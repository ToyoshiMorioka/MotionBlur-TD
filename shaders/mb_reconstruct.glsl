// ぼかす（GLSL TOP の画素シェーダ）。McGuire ほか「A Reconstruction Filter for Plausible Motion Blur」（I3D 2012）
// 各画素で、まわりのタイルでいちばん大きな動きの向きに点を取り、次の重みで平均する
//   ・手前にある点が、自分のぼかしの範囲でこの画素に届くなら、その点の色を混ぜる（動く物が手前の背景にかぶる）
//   ・奥にある点は、この画素自身がぼけて届く範囲なら混ぜる（動く物の向こうの背景が透けて見える）
//   ・同じくらいの奥行きで、どちらも動いているなら混ぜる
// 入力 0：ぼかす絵、入力 1：動き（rg = 画素、b = カメラからの距離、a = 物があるか）、入力 2：mb_neighbormax の出力
// 出力：ぼかした絵（入力と同じ形式。a も同じ重みで平均する）

uniform vec4 uMB;     // x = Shutter、y = Max Blur（画素）、z = Samples、w = タイルの大きさ K（画素）
uniform float uFrame; // 点の取り方を画素ごと・フレームごとにずらす

const float FAR = 1e6;   // 物の無い画素（背景）の奥行き

vec2 radius(vec2 v)
{
	vec2 r = v * uMB.x * 0.5;
	float l = length(r);
	return l > uMB.y ? r * (uMB.y / l) : r;
}

// a が b より手前なら 1、奥なら 0（その間はなめらかに。幅は距離の 1%）
float softDepth(float a, float b)
{
	return clamp(1.0 - (a - b) / max(0.01 * min(a, b), 1e-3), 0.0, 1.0);
}

float cone(float d, float len)
{
	return clamp(1.0 - d / len, 0.0, 1.0);
}

float cylinder(float d, float len)
{
	return 1.0 - smoothstep(0.95 * len, 1.05 * len, d);
}

layout(location = 0) out vec4 fragColor;

void main()
{
	ivec2 ix = ivec2(gl_FragCoord.xy);
	ivec2 res = textureSize(sTD2DInputs[0], 0);
	vec4 cX = texelFetch(sTD2DInputs[0], ix, 0);
	int K = int(uMB.w + 0.5);
	vec2 vN = texelFetch(sTD2DInputs[2], ix / K, 0).rg;
	// まわりで半画素より大きく動く物が無ければ、そのまま
	if (dot(vN, vN) <= 0.25) {
		fragColor = cX;
		return;
	}
	vec4 VX = texelFetch(sTD2DInputs[1], ix, 0);
	vec2 vX = VX.a > 0.0 ? radius(VX.rg) : vec2(0.0);
	float zX = VX.a > 0.0 ? VX.b : FAR;
	float lenX = max(length(vX), 0.5);

	float w = 1.0 / lenX;
	vec4 sum = cX * w;
	int S = max(int(uMB.z + 0.5), 1);
	float jitter = fract(52.9829189 * fract(dot(gl_FragCoord.xy, vec2(0.06711056, 0.00583715))) + uFrame * 0.61803399) - 0.5;
	float lenN = length(vN);
	for (int i = 0; i < S; i++) {
		float t = mix(-1.0, 1.0, (float(i) + jitter + 1.0) / (float(S) + 1.0));
		ivec2 iy = clamp(ivec2(floor(gl_FragCoord.xy + vN * t)), ivec2(0), res - 1);
		if (iy == ix) continue;
		float d = abs(t) * lenN;
		vec4 VY = texelFetch(sTD2DInputs[1], iy, 0);
		vec2 vY = VY.a > 0.0 ? radius(VY.rg) : vec2(0.0);
		float zY = VY.a > 0.0 ? VY.b : FAR;
		float lenY = max(length(vY), 0.5);
		float f = softDepth(zY, zX);   // Y が手前
		float b = softDepth(zX, zY);   // X が手前
		float a = f * cone(d, lenY) + b * cone(d, lenX) + cylinder(d, lenY) * cylinder(d, lenX) * 2.0;
		w += a;
		sum += texelFetch(sTD2DInputs[0], iy, 0) * a;
	}
	fragColor = sum / w;
}
