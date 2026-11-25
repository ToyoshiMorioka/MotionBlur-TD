# MotionBlur と VoxelConeTracing-TD を組み合わせた見本
# VoxelConeTracing-TD の見本（build_vct_sample.py）をそのまま組み、ガラスを重ねた絵とトーンマップの間に MotionBlur を入れる。
# VoxelConeTracing-TD のファイルは何も変えない。
#
# 使い方（TouchDesigner 2025）:
#   1. VoxelConeTracing-TD（https://github.com/ToyoshiMorioka/VoxelConeTracing-TD）を、このフォルダの隣に置く
#      （…/MotionBlur-TD と …/VoxelConeTracing-TD。別の場所なら、exec の前に VCT_ROOT = 'C:/.../VoxelConeTracing-TD'）
#   2. 先に build_mb_tox.py で MotionBlur.tox を作っておく
#   3. Textport（Alt+T / Option+T）に次の1行を貼って Enter
#      exec(open(project.folder + '/build_mb_with_vct.py', encoding='utf-8').read())
#
# /project1/vct_mb_sample が作られる（同名があれば作り直す）。結果は中の out。

import os

ROOT = globals().get('MB_ROOT', project.folder)


def find_vct_root():
	if 'VCT_ROOT' in globals():
		return VCT_ROOT
	parent_dir = os.path.dirname(os.path.abspath(ROOT))
	for name in ('VoxelConeTracing-TD', 'VoxelCT_TD'):
		d = os.path.join(parent_dir, name)
		if os.path.exists(os.path.join(d, 'build_vct_sample.py')):
			return d
	raise RuntimeError('VoxelConeTracing-TD が見つかりません。exec の前に VCT_ROOT = "…/VoxelConeTracing-TD" を実行してください')


def build():
	vct_root = find_vct_root()
	# VCT の見本を組む（/project1/vct_sample にできる）。VCT のスクリプトは VCT_ROOT を見て tox とモデルを読む
	g = dict(globals())
	g['VCT_ROOT'] = vct_root
	exec(open(os.path.join(vct_root, 'build_vct_sample.py'), encoding='utf-8').read(), g)
	parent_comp = op('/project1') or root
	old = parent_comp.op('vct_mb_sample')
	if old:
		old.destroy()
	base = parent_comp.op('vct_sample')
	base.name = 'vct_mb_sample'
	base.nodeY = -2400

	# ガラスを重ねた絵（over_glass）→ MotionBlur → トーンマップ
	over = base.op('over_glass')
	tone = base.op('tonemap')
	mb = base.loadTox(os.path.join(ROOT, 'tox', 'MotionBlur.tox'))
	mb.name = 'MotionBlur'
	mb.nodeX, mb.nodeY = over.nodeX, over.nodeY + 200
	mb.inputConnectors[0].connect(over)
	tone.inputConnectors[0].connect(mb.outputConnectors[0])
	# カメラと解像度は render_opaque から。動きは、ガラス（glass_*）も含めて描く
	mb.par.Render = 'render_opaque'
	mb.par.Geometry = 'geo_* glass_*'
	print('----', base.path)
	print('組み合わせの見本を組みました。', base.path + '/out', 'を見てください。VCT：', vct_root)
	return base


build()
