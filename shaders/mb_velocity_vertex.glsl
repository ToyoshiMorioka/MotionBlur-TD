// 動きを描く GLSL MAT の頂点シェーダ（MotionBlur の slotN ごとに 1 つ）
// 形は元の Geometry COMP の中の座標のまま（slotN は動かさない）。PrevP は前のフレームの点の位置（同じ座標）
// 世界での置き方（Geometry COMP の行列）は、毎フレームの処理（runtime）が今と前のフレームの分を入れる。
// 物の移動・回転は行列の違いで、変形は P と PrevP の違いで、カメラの動きは投影 × ビューの違いで、まとめて動きになる

uniform vec4 uWorld0;    // 今のフレームの、元の Geometry COMP の世界での行列（4 行）
uniform vec4 uWorld1;
uniform vec4 uWorld2;
uniform vec4 uWorld3;
uniform vec4 uCurVP0;    // 今のフレームのカメラの「投影 × ビュー」（4 行）
uniform vec4 uCurVP1;
uniform vec4 uCurVP2;
uniform vec4 uCurVP3;
uniform vec4 uPrevMVP0;  // 前のフレームの「投影 × ビュー × 世界での行列」（4 行）
uniform vec4 uPrevMVP1;
uniform vec4 uPrevMVP2;
uniform vec4 uPrevMVP3;

out Vertex
{
	vec4 curClip;
	vec4 prevClip;
	float depth;
} oVert;

vec4 rows(vec4 r0, vec4 r1, vec4 r2, vec4 r3, vec4 p)
{
	return vec4(dot(r0, p), dot(r1, p), dot(r2, p), dot(r3, p));
}

void main()
{
	vec4 local = vec4(TDPos(), 1.0);
	vec4 worldPos = rows(uWorld0, uWorld1, uWorld2, uWorld3, local);
	oVert.curClip = rows(uCurVP0, uCurVP1, uCurVP2, uCurVP3, worldPos);
	oVert.prevClip = rows(uPrevMVP0, uPrevMVP1, uPrevMVP2, uPrevMVP3, vec4(TDAttrib_PrevP(), 1.0));
	oVert.depth = -(uTDMats[TDCameraIndex()].cam * worldPos).z;
	gl_Position = TDWorldToProj(worldPos);
}
