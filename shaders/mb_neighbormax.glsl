// まわり 3×3 のタイルの最大の動き（GLSL TOP の画素シェーダ。タイルの大きさのまま）
// 入力 0：mb_tilemax の出力
// 出力：rg = まわりでいちばん長いぼかしの半径、b = その長さ

layout(location = 0) out vec4 fragColor;

void main()
{
	ivec2 id = ivec2(gl_FragCoord.xy);
	ivec2 res = textureSize(sTD2DInputs[0], 0);
	vec4 best = vec4(0.0);
	for (int y = -1; y <= 1; y++)
	for (int x = -1; x <= 1; x++) {
		vec4 t = texelFetch(sTD2DInputs[0], clamp(id + ivec2(x, y), ivec2(0), res - 1), 0);
		if (t.b > best.b) best = t;
	}
	fragColor = vec4(best.rgb, 1.0);
}
