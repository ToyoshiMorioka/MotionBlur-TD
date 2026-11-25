// 前のフレームの点の位置を付ける（GLSL POP、点ごと）
// 入力 0：今のフレームの形（元の Geometry COMP の中の座標）
// 入力 1：前のフレームの形（Feedback POP）。点が動いている形だけ。止まっている形では入力 0 と同じ物を runtime がつなぐ
//         （Feedback POP は毎フレーム計算し直されるので、要らない時はつながない）
// 出力：入力 0 に、前のフレームの点の位置 PrevP を足したもの
// 点の数が違う時（形が変わった、最初のフレーム）は、PrevP = P（そのフレームは変形による動き 0）

void main()
{
	const uint id = TDIndex();
	if (id >= TDNumElements())
		return;
	vec3 p = TDIn_P();
	PrevP[id] = TDInputNumPoints(1) == TDInputNumPoints(0) ? TDIn_P(1, id) : p;
}
