# MotionBlur の見本：ふつうの PBR MAT の物（回る箱、左右に動く球、ノイズで揺れる形）と、ゆっくり振れるカメラ
#
# 使い方（TouchDesigner 2025）:
#   先に build_mb_tox.py で tox を作っておく。Textport（Alt+T / Option+T）に次の1行を貼って Enter
#   exec(open(project.folder + '/build_mb_sample.py', encoding='utf-8').read())
#
# /project1/mb_sample が作られる（同名があれば作り直す）。結果は中の out。ぼかす前は render1（リニアのまま）。
# .toe が別のフォルダにあるときは、exec の前に MB_ROOT = 'C:/.../MotionBlur_TD' を実行しておく。

import os

# 既定は、開いている .toe のフォルダ
ROOT = globals().get('MB_ROOT', project.folder)
TOX_DIR = os.path.join(ROOT, 'tox')
problems = []


def setp(o, **kw):
	for name, v in kw.items():
		p = getattr(o.par, name, None)
		if p is None:
			problems.append('{}: パラメータ {} が見つからない'.format(o.path, name))
			continue
		try:
			if isinstance(v, str) and v.startswith('='):
				p.expr = v[1:]
				p.mode = ParMode.EXPRESSION
			else:
				p.val = v
		except Exception as e:
			problems.append('{}.{} = {!r}: {}'.format(o.path, name, v, e))


def at(o, x, y):
	o.nodeX, o.nodeY = x, y
	return o


def material(base, name, color, rough=0.5, metal=0.0):
	m = base.create(pbrMAT, name)
	setp(m, basecolorr=color[0], basecolorg=color[1], basecolorb=color[2], roughness=rough, metallic=metal)
	return m


def geo(base, name, mat, t=(0, 0, 0)):
	g = base.create(geometryCOMP, name)
	for c in list(g.children):
		c.destroy()
	setp(g, tx=t[0], ty=t[1], tz=t[2], material=mat.name)
	return g


def show(pop):
	pop.render = pop.display = True
	return pop


def note(base, name, title, body, members, color):
	a = base.create(annotateCOMP, name)
	left = min(o.nodeX for o in members) - 40
	right = max(o.nodeX + o.nodeWidth for o in members) + 40
	bottom = min(o.nodeY for o in members) - 40
	top = max(o.nodeY + o.nodeHeight for o in members) + 90
	a.nodeX, a.nodeY, a.nodeWidth, a.nodeHeight = left, bottom, right - left, top - bottom
	setp(a, Mode='annotate', Titletext=title, Bodytext=body,
	     Backcolorr=color[0], Backcolorg=color[1], Backcolorb=color[2], Backcoloralpha=0.85)


def build():
	parent_comp = op('/project1') or root
	old = parent_comp.op('mb_sample')
	if old:
		old.destroy()
	base = parent_comp.create(baseCOMP, 'mb_sample')
	base.nodeX, base.nodeY = 0, -1800
	COL, ROW = 220, 180

	# --- 動かすための時計（absTime を直接使わず、Speed CHOP で積み上げる）
	rates = at(base.create(constantCHOP, 'rates'), 0, -4 * ROW)
	setp(rates, const0name='spin', const0value=720, const1name='t', const1value=2.0)
	clock = at(base.create(speedCHOP, 'clock'), COL, -4 * ROW)
	clock.inputConnectors[0].connect(rates)
	clock_out = at(base.create(nullCHOP, 'clock_out'), 2 * COL, -4 * ROW)
	clock_out.inputConnectors[0].connect(clock)
	swing = at(base.create(lfoCHOP, 'swing'), 3 * COL, -4 * ROW)
	setp(swing, frequency=1.2, amp=1.8)
	cam_swing = at(base.create(lfoCHOP, 'cam_swing'), 4 * COL, -4 * ROW)
	setp(cam_swing, frequency=0.15, amp=4)

	# --- 材質（上）と形（下）
	floor_m = at(material(base, 'mat_floor', (0.6, 0.6, 0.62), rough=0.8, metal=0.0), 0, 0)
	box_m = at(material(base, 'mat_box', (0.95, 0.45, 0.1), rough=0.4, metal=0.0), COL, 0)
	ball_m = at(material(base, 'mat_ball', (0.15, 0.4, 0.95), rough=0.3, metal=0.0), 2 * COL, 0)
	blob_m = at(material(base, 'mat_blob', (0.2, 0.85, 0.35), rough=0.5, metal=0.0), 3 * COL, 0)

	floor = at(geo(base, 'geo_floor', floor_m, (0, -1, 0)), 0, -ROW)
	setp(floor, rx=-90)
	setp(show(floor.create(gridPOP, 'grid')), sizex=10, sizey=10, rows=2, cols=2)

	box = at(geo(base, 'geo_box', box_m, (-2.2, -0.35, -0.5)), COL, -ROW)
	setp(box, ry="=op('clock_out')['spin']", rx=25)
	setp(show(box.create(boxPOP, 'box')), sizex=1.0, sizey=1.0, sizez=1.0)

	ball = at(geo(base, 'geo_ball', ball_m, (0, -0.55, 1.0)), 2 * COL, -ROW)
	setp(ball, tx="=op('swing')['chan1']")
	setp(show(ball.create(spherePOP, 'sphere')), freq=8, radx=0.45, rady=0.45, radz=0.45)

	# 変形する形：球の点を 4 次元ノイズで動かす（形の中の点が動く。Geometry COMP は動かない）
	blob = at(geo(base, 'geo_blob', blob_m, (1.8, -0.2, -0.8)), 3 * COL, -ROW)
	sp = blob.create(spherePOP, 'sphere')
	setp(sp, freq=12, radx=0.6, rady=0.6, radz=0.6)
	nz = show(blob.create(noisePOP, 'noise'))
	nz.inputConnectors[0].connect(sp)
	setp(nz, type='simplex4d', amp0=0.18, period=1.4, harmon=1, t4d="=op('../clock_out')['t']")
	sp.nodeX, nz.nodeX = 0, 220

	# --- 光源・カメラ・描画
	x0 = 5 * COL
	light = at(base.create(lightCOMP, 'light1'), x0, 0)
	setp(light, lighttype='point', tx=2, ty=4, tz=4, dimmer=3.0, attenuated=False, shadowtype='off')
	light2 = at(base.create(lightCOMP, 'light2'), x0, -ROW)
	setp(light2, lighttype='distant', rx=-30, ry=-140, dimmer=0.8, shadowtype='off')
	cam = at(base.create(cameraCOMP, 'cam1'), x0, -2 * ROW)
	setp(cam, tz=8, ty=1.2, rx=-8, ry="=op('cam_swing')['chan1']")
	render = at(base.create(renderTOP, 'render1'), x0 + COL, 0)
	setp(render, camera=cam.name, geometry='geo_*', lights='light1 light2', outputresolution='custom',
	     resolutionw=1280, resolutionh=720, format='rgba16float', antialias='aa4',
	     bgcolorr=0.05, bgcolorg=0.05, bgcolorb=0.06, bgcolora=1)

	mb = base.loadTox(os.path.join(TOX_DIR, 'MotionBlur.tox'))
	mb.name = 'MotionBlur'
	at(mb, x0 + 2 * COL, 0)
	mb.inputConnectors[0].connect(render)
	# 見本では効果が見えやすいよう、1 フレームの間ずっとシャッターが開いている状態にする（tox の初期値は 0.5）
	setp(mb, Render=render.name, Shutter=1.0)
	# PBR MAT の出力はリニアな値なので、画面用にガンマをかける（モーションブラーはリニアのままかける）
	gamma = at(base.create(levelTOP, 'gamma'), x0 + 3 * COL, 0)
	gamma.inputConnectors[0].connect(mb.outputConnectors[0])
	setp(gamma, gamma1=2.2)
	out = at(base.create(nullTOP, 'out'), x0 + 4 * COL, 0)
	out.inputConnectors[0].connect(gamma)
	out.viewer = True

	note(base, 'note_scene', '材質と形', '列ごとに、上が PBR MAT、その下がその材質を使う Geometry COMP。'
	     '箱は回り、球は左右に動き、緑の形はノイズで揺れる（形の中の点が動く）。',
	     [floor_m, box_m, ball_m, blob_m, floor, box, ball, blob], (0.20, 0.47, 0.55))
	note(base, 'note_render', '描画とモーションブラー', 'render1 の絵を MotionBlur に通し、ガンマをかけて out へ。'
	     'MotionBlur の Render には render1 を指定（カメラと形の一覧をそこから取る）。カメラもゆっくり振れる。',
	     [light, light2, cam, render, mb, gamma, out], (0.47, 0.28, 0.62))
	note(base, 'note_clock', '動かすための時計', 'rates（箱の回転の速さ・ノイズの時間の進み方）→ clock（Speed CHOP で積み上げる）。'
	     'swing：球の左右、cam_swing：カメラの振れ。',
	     [rates, clock, clock_out, swing, cam_swing], (0.4, 0.4, 0.4))

	print('----', base.path)
	if problems:
		print('次の設定は手動で確認してください:')
		for p in problems:
			print('  -', p)
	else:
		print('見本を組みました。', base.path + '/out', 'を見てください。')
	return base


build()
