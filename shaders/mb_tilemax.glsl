// タイルごとの最大の動き（GLSL TOP の画素シェーダ。横と縦の 2 回に分けて使う）
// McGuire ほか（2012）の TileMax。ぼかしの半径はタイルの大きさ（= Max Blur）を超えないので、
// まわり 3×3 のタイルを見れば、この画素に届くぼかしを漏らさない。
// 1 回で K×K 画素を読むと、出力の画素が少なく並列に動けず遅かった（K = 24 で 1.3 ms。2026-11-25 実機で確認）。
// 1 回目（横）：入力は動き（rg = 画素、a = 物があるか）。横 K 画素ごとの最大を、Shutter を掛け Max Blur で切ったぼかしの半径で出す
// 2 回目（縦）：入力は 1 回目の出力。縦 K 画素ごとの最大
// 出力：rg = いちばん長いぼかしの半径、b = その長さ

uniform vec4 uMB;     // x = Shutter、y = Max Blur（画素）、z = Samples、w = タイルの大きさ K（画素）
uniform vec2 uPass;   // x = 向き（0 = 横、1 = 縦）、y = 1 なら入力は動き（1 回目）

vec2 radius(vec2 v)
{
	vec2 r = v * uMB.x * 0.5;
	float l = length(r);
	return l > uMB.y ? r * (uMB.y / l) : r;
}

layout(location = 0) out vec4 fragColor;

void main()
{
	int K = int(uMB.w + 0.5);
	ivec2 res = textureSize(sTD2DInputs[0], 0);
	ivec2 id = ivec2(gl_FragCoord.xy);
	ivec2 step = uPass.x < 0.5 ? ivec2(1, 0) : ivec2(0, 1);
	ivec2 base = uPass.x < 0.5 ? ivec2(id.x * K, id.y) : ivec2(id.x, id.y * K);
	vec2 best = vec2(0.0);
	float bestLen = 0.0;
	for (int k = 0; k < K; k++) {
		ivec2 q = base + step * k;
		if (any(greaterThanEqual(q, res))) break;
		vec4 v = texelFetch(sTD2DInputs[0], q, 0);
		vec2 r;
		if (uPass.y > 0.5) {
			if (v.a <= 0.0) continue;
			r = radius(v.rg);
		} else {
			r = v.rg;
		}
		float l = dot(r, r);
		if (l > bestLen) {
			bestLen = l;
			best = r;
		}
	}
	fragColor = vec4(best, sqrt(bestLen), 1.0);
}
