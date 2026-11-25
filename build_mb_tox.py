# MotionBlur.tox を作る
#
# 使い方（TouchDesigner 2025）:
#   このフォルダに .toe を保存してから（または MB_sample.toe を開いて）、Textport（Alt+T / Option+T）に次の1行を貼って Enter
#   exec(open(project.folder + '/build_mb_tox.py', encoding='utf-8').read())
#
# /project1/mb_tox_build の中に MotionBlur を作り、tox/MotionBlur.tox に保存する。
# .toe が別のフォルダにあるときは、exec の前に MB_ROOT = 'C:/.../MotionBlur_TD' を実行しておく。
#
# 使い方の流れ
#   ・ぼかしたい絵（Render TOP の出力、またはそれを重ねた絵）を MotionBlur の入力につなぐ
#   ・Render に、その絵を描いた Render TOP を指定する（カメラ・解像度・形の一覧をそこから取る）
#   ・出力を、露出・トーンマップなどの後ろの処理へ

import os

# 既定は、開いている .toe のフォルダ
ROOT = globals().get('MB_ROOT', project.folder)
SHADERS = os.path.join(ROOT, 'shaders')
TOX_DIR = os.path.join(ROOT, 'tox')

GX, GY = 380, 260
problems = []


def setp(o, **kw):
	"""パラメータを設定する。'=' で始まる文字列は式として設定。失敗しても止めずに記録する。"""
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


def place(o, x, y):
	o.nodeX, o.nodeY = int(x * GX), int(-y * GY)


def connect(dst, *srcs):
	for i, s in enumerate(srcs):
		dst.inputConnectors[i].connect(s)


def drop_docked(o):
	for d in list(o.docked):
		d.destroy()


def text_dat(base, name, path, x, y, language='glsl'):
	"""ファイルの中身を DAT に入れる（ファイルとは同期させない。tox だけで動くように）。"""
	d = base.create(textDAT, name)
	d.text = open(path, encoding='utf-8').read()
	setp(d, language=language)
	place(d, x, y)
	return d


def shader(base, name, filename, x, y):
	return text_dat(base, name, os.path.join(SHADERS, filename), x, y)


def uniforms(glsl, items):
	"""items: [(名前, (x, y, z, w))]。値は数か式（'=' で始まる文字列）。"""
	glsl.seq.vec.numBlocks = len(items)
	for i, (uname, vals) in enumerate(items):
		if not isinstance(vals, (tuple, list)):
			vals = (vals,)
		kw = {'vec{}name'.format(i): uname}
		for c, v in zip('xyzw', vals):
			kw['vec{}value{}'.format(i, c)] = v
		setp(glsl, **kw)


def pixel_top(base, name, dat, x, y, op_type=None):
	g = base.create(op_type or glslTOP, name)
	drop_docked(g)
	place(g, x, y)
	setp(g, pixeldat=dat.name, inputfiltertype='nearest')
	return g


def note(base, name, title, body, x0, y0, x1, y1, color=(0.3, 0.3, 0.3)):
	a = base.create(annotateCOMP, name)
	left, right = x0 * GX - 50, x1 * GX + 260
	top, bottom = -y0 * GY + 190, -y1 * GY - 60
	a.nodeX, a.nodeY = int(left), int(bottom)
	a.nodeWidth, a.nodeHeight = int(right - left), int(top - bottom)
	setp(a, Mode='annotate', Titletext=title, Bodytext=body,
	     Backcolorr=color[0], Backcolorg=color[1], Backcolorb=color[2], Backcoloralpha=0.85)


def num_par(page, name, label, val, lo, hi, integer=False):
	p = (page.appendInt if integer else page.appendFloat)(name, label=label)[0]
	p.normMin, p.normMax = lo, hi
	p.default = val
	p.val = val
	return p


# ======================================================================

def mb_pars(mb):
	s = mb.appendCustomPage('Motion Blur')
	s.appendTOP('Render', label='Render（ぼかす絵を描いた Render TOP。カメラ・解像度・形の一覧をここから取る）')
	p = s.appendStr('Geometry', label='Geometry（動きを描く Geometry COMP。空なら Render と同じ）')[0]
	p.default = p.val = ''
	num_par(s, 'Shutter', 'Shutter（シャッターの開いている割合。0.5 で 1 フレームの半分の時間ぶんぼける）', 0.5, 0, 1)
	num_par(s, 'Maxblur', 'Max Blur（ぼかしの最大の半径。画素）', 24, 2, 64, integer=True)
	num_par(s, 'Samples', 'Samples（ぼかしに使う点の数）', 15, 3, 41, integer=True)
	i = mb.appendCustomPage('Info')
	p = i.appendStr('Status', label='Status（状況）')[0]
	p.readOnly = True
	p = i.appendInt('Motionblur', label='Motion Blur（目印）')[0]
	p.default = p.val = 1
	p.readOnly = True


def build_mb(holder):
	mb = holder.create(baseCOMP, 'MotionBlur')
	mb.par.parentshortcut = 'MotionBlur'
	place(mb, 0, 0)
	mb_pars(mb)
	R = 'parent().par.Render.eval()'

	# --- 毎フレームの処理（slotN が並ぶ左下と重ならないよう、左上に置く）
	text_dat(mb, 'runtime', os.path.join(ROOT, 'scripts', 'mb_runtime.py'), -2.5, -1, 'python')
	ex = mb.create(executeDAT, 'mb_exec')
	place(ex, -2.5, -0.4)
	ex.text = ('# フレームの始めに、形の一覧とカメラの行列を更新する（中身は runtime）\n'
	           'def onFrameStart(frame):\n'
	           '\top(\'runtime\').module.update(parent())\n'
	           '\treturn\n')
	setp(ex, framestart=True, active=True)

	# --- シェーダの DAT（いちばん下の段に流れの順）
	d_prev = shader(mb, 'prevp_cs', 'mb_prevp.glsl', -2, 4)
	d_vv = shader(mb, 'velocity_vertex', 'mb_velocity_vertex.glsl', -1, 4)
	d_vp = shader(mb, 'velocity_pixel', 'mb_velocity_pixel.glsl', 0, 4)
	d_tile = shader(mb, 'tilemax_ps', 'mb_tilemax.glsl', 1, 4)
	d_nb = shader(mb, 'neighbormax_ps', 'mb_neighbormax.glsl', 2, 4)
	d_rec = shader(mb, 'reconstruct_ps', 'mb_reconstruct.glsl', 3, 4)

	# --- 入力（ぼかす絵）
	inp = mb.create(inTOP, 'in1')
	place(inp, -1, -1)

	# --- ① 動きを描く（slotN を、Render のカメラ・解像度で。材質は slotN ごとに runtime が作る）
	vel = mb.create(renderTOP, 'velocity')
	place(vel, 0, 0)
	setp(vel, camera="=op('runtime').module.camera_of({0})".format(R), geometry='slot*', lights='',
	     format='rgba16float', antialias='aa1', outputresolution='custom',
	     resolutionw='=({0}.width if {0} else 16)'.format(R),
	     resolutionh='=({0}.height if {0} else 16)'.format(R),
	     bgcolorr=0, bgcolorg=0, bgcolorb=0, bgcolora=0)

	# --- ② タイルごとの最大の動き → まわり 3×3 の最大
	MB = ('=parent().par.Shutter', '=parent().par.Maxblur', '=parent().par.Samples', '=max(1, parent().par.Maxblur)')
	K = 'max(1, parent().par.Maxblur)'
	tile_x = pixel_top(mb, 'tilemax_x', d_tile, 1, 0)
	connect(tile_x, vel)
	setp(tile_x, format='rgba16float', outputresolution='custom',
	     resolutionw="=max(1, -(-op('velocity').width // {}))".format(K), resolutionh="=op('velocity').height")
	uniforms(tile_x, [('uMB', MB), ('uPass', (0, 1))])
	tile = pixel_top(mb, 'tilemax', d_tile, 1.5, 0)
	connect(tile, tile_x)
	setp(tile, format='rgba16float', outputresolution='custom',
	     resolutionw="=op('tilemax_x').width", resolutionh="=max(1, -(-op('velocity').height // {}))".format(K))
	uniforms(tile, [('uMB', MB), ('uPass', (1, 0))])
	nb = pixel_top(mb, 'neighbormax', d_nb, 2.2, 0)
	connect(nb, tile)
	setp(nb, format='rgba16float')

	# --- ③ ぼかす
	rec = pixel_top(mb, 'reconstruct', d_rec, 3, -1, glslmultiTOP)
	connect(rec, inp, vel, nb)
	setp(rec, format='useinput')
	uniforms(rec, [('uMB', MB), ('uFrame', '=absTime.frame')])
	out = mb.create(outTOP, 'out1')
	place(out, 4, -1)
	connect(out, rec)

	note(mb, 'note_about', 'MotionBlur ── 速度バッファ方式のモーションブラー（McGuire ほか 2012）',
	     '入力にぼかす絵、Render にその絵を描いた Render TOP を指定する。出力はぼかした絵。\n'
	     'slotN：形 1 つにつき 1 つ（runtime が作り直す）。点が動いている形にだけ、Feedback POP で前のフレームの点の位置 PrevP を付ける。'
	     '形の世界での置き方とカメラの、今と前のフレームの行列は、runtime が slotN の材質に毎フレーム入れる。\n'
	     'velocity：今と前のフレームの位置を、それぞれのカメラで画面に写した差（画素）と奥行きを描く。\n'
	     'tilemax_x → tilemax → neighbormax：Max Blur 画素四方のタイルごとの最大の動き（横と縦に分けて求める）。reconstruct：その向きに点を取り、奥行きと動きで重みを付けて平均する。',
	     -2.5, -2.4, 4, -2.4)
	note(mb, 'note_shaders', 'シェーダ（tox だけで動くよう、ファイルの中身を写してある）',
	     'prevp_cs（GLSL POP）→ velocity_vertex・velocity_pixel（GLSL MAT）→ tilemax（横・縦の 2 回）→ neighbormax → reconstruct',
	     -2, 4, 3, 4)
	return mb


def build():
	parent_comp = op('/project1') or root
	old = parent_comp.op('mb_tox_build')
	if old:
		old.destroy()
	holder = parent_comp.create(baseCOMP, 'mb_tox_build')
	holder.nodeX, holder.nodeY = 0, -1400
	mb = build_mb(holder)
	os.makedirs(TOX_DIR, exist_ok=True)
	mb.save(os.path.join(TOX_DIR, 'MotionBlur.tox'))
	print('----', holder.path)
	if problems:
		print('次の設定は手動で確認してください:')
		for p in problems:
			print('  -', p)
	else:
		print('tox を保存しました：', TOX_DIR)
	return holder


build()
