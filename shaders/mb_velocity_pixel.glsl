// 動きを描く GLSL MAT の画素シェーダ
// 出力：rg = 前のフレームから今までの動き（画素）、b = カメラからの距離、a = 1（物がある）

in Vertex
{
	vec4 curClip;
	vec4 prevClip;
	float depth;
} iVert;

layout(location = 0) out vec4 fragColor;

void main()
{
	TDCheckDiscard();
	vec2 res = 1.0 / uTDGeneral.viewport.zw;
	vec2 vel = vec2(0.0);
	// 前の位置がカメラの後ろにあった時は、動きを求められないので 0 にする
	if (iVert.prevClip.w > 1e-4 && iVert.curClip.w > 1e-4)
		vel = (iVert.curClip.xy / iVert.curClip.w - iVert.prevClip.xy / iVert.prevClip.w) * 0.5 * res;
	fragColor = vec4(vel, iVert.depth, 1.0);
}
