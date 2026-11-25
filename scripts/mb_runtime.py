# MotionBlur の中で毎フレーム動く処理（MotionBlur の中の DAT「runtime」に入る）
# mb_exec（Execute DAT）が、フレームの始めに update(MotionBlur) を呼ぶ。
#
#   ・形の一覧が変わったら、slotN（Geometry COMP 1 つにつき 1 つ）を作り直す（0.25 秒ごとに調べる）
#   ・Render のカメラと各形の、今と前のフレームの行列を、slotN の材質に入れる（毎フレーム）
#   ・点が動いている形にだけ、前のフレームの形（Feedback POP）をつなぐ
#   ・状況を Status パラメータに書く


# ---------- 一覧を読む

def camera_of(render):
	"""Render TOP の Camera に指定された最初の Camera COMP。無ければ None。"""
	if render is None:
		return None
	c = render.par.camera.eval()
	if isinstance(c, str):
		names = c.split()
		c = render.parent().op(names[0]) if names else None
	return c if c is not None and c.OPType == 'cameraCOMP' else None


def render_op(geo):
	"""Geometry COMP の中で描画フラグの立っている POP か SOP。無ければ None。"""
	for c in geo.children:
		if c.family in ('POP', 'SOP') and c.render:
			return c
	return None


def geo_chain(g):
	"""g と、その上にある Geometry COMP（親・祖父…）。"""
	chain = []
	o = g
	while o is not None and o.OPType == 'geometryCOMP':
		chain.append(o)
		o = o.parent()
	return chain


def scene_items(mb, render):
	"""(Geometry COMP, 描く POP/SOP) の一覧と、飛ばした Geometry COMP の名前。"""
	pattern = mb.par.Geometry.eval().strip()
	if pattern:
		base = mb.parent()
		roots = []
		for tok in pattern.split():
			for o in base.ops(tok):
				if o not in roots:
					roots.append(o)
	else:
		roots = list(render.par.geometry.evalOPs()) if render else []
	# Render TOP と同じく、Geometry COMP の中にある Geometry COMP（子・孫）も含める
	geos = []
	for g in roots:
		if g.OPType != 'geometryCOMP':
			continue
		for h in [g] + g.findChildren(type=geometryCOMP):
			if h not in geos:
				geos.append(h)
	items, skipped = [], []
	for g in geos:
		# 自分か親のどれかの Render がオフなら描かれないので、入れない
		if any(not a.par.render.eval() for a in geo_chain(g)):
			continue
		r = render_op(g)
		if r is None:
			if not g.findChildren(type=geometryCOMP, depth=1):
				skipped.append(g.name)
			continue
		items.append((g, r))
	return items, skipped


# ---------- スロット

def setp(o, **kw):
	for name, v in kw.items():
		p = getattr(o.par, name)
		if isinstance(v, str) and v.startswith('='):
			p.expr = v[1:]
			p.mode = ParMode.EXPRESSION
		else:
			p.val = v


def make_slot(mb, i, geo, rop):
	"""slotN：形を元の Geometry COMP の中の座標のまま持ち、前のフレームの点の位置 PrevP を付けて描く Geometry COMP。
	世界での置き方は、slotN の中の材質 mat に毎フレーム行列で入れる（POP で動かすと、止まっている形も毎フレーム計算し直しになるため）。"""
	s = mb.create(geometryCOMP, 'slot{}'.format(i))
	s.nodeX, s.nodeY = -800 + (i % 3) * 230, -400 - (i // 3) * 180
	for c in list(s.children):
		c.destroy()
	if rop.family == 'POP':
		src = s.create(selectPOP, 'src')
		setp(src, pop=rop.path)
	else:
		src = s.create(soptoPOP, 'src')
		setp(src, sop=rop.path)
	# 1 フレーム前の src。点が動いている形の時だけ prevp につなぐ（update_slots）
	prev = s.create(feedbackPOP, 'prev')
	prev.inputConnectors[0].connect(src)
	setp(prev, targetpop=src.name)
	add = s.create(glslPOP, 'prevp')
	for d in list(add.docked):
		d.destroy()
	add.inputConnectors[0].connect(src)
	add.inputConnectors[1].connect(src)
	add.seq.attr.numBlocks = 1
	setp(add, computedat='../prevp_cs', attrclass='point', outputattrs='PrevP',
	     attr0name='custom', attr0customname='PrevP', attr0type='float', attr0numcomps='3')
	out = s.create(nullPOP, 'out')
	out.inputConnectors[0].connect(add)
	out.render = out.display = True
	# 材質：形ごとに行列が違うので、slotN ごとに持つ
	mat = s.create(glslMAT, 'mat')
	for d in list(mat.docked):
		d.destroy()
	setp(mat, vdat='../velocity_vertex', pdat='../velocity_pixel')
	mat.seq.attr.numBlocks = 1
	setp(mat, attr0name='PrevP', attr0type='float3')
	names = ['uWorld{}', 'uCurVP{}', 'uPrevMVP{}']
	mat.seq.vec.numBlocks = 12
	for b, nm in enumerate(names):
		for r in range(4):
			k = b * 4 + r
			setp(mat, **{'vec{}name'.format(k): nm.format(r)})
	for k, o in enumerate([src, add, out]):
		o.nodeX, o.nodeY = k * 220, 0
	prev.nodeX, prev.nodeY = 220, -180
	mat.nodeX, mat.nodeY = 440, 200
	setp(s, material=mat.path)
	s.comment = geo.path
	s.storage['geo'] = geo
	s.storage['rop'] = rop
	return s


def rebuild_slots(mb, items):
	for c in list(mb.children):
		if c.name.startswith('slot'):
			c.destroy()
	for i, (g, r) in enumerate(items):
		make_slot(mb, i, g, r)


def signature(items):
	return tuple((g.path, r.path, r.family) for g, r in items)


# ---------- カメラ

def view_proj(cam, w, h):
	"""投影 × ビューの行列（tdu.Matrix。列ベクトルに掛ける形：M * 点）。"""
	view = tdu.Matrix(cam.worldTransform)
	view.invert()
	return cam.projection(w, h) * view


def mat_rows(m):
	return [tuple(m[r, c] for c in range(4)) for r in range(4)]


def set_rows(mat, first_block, rows):
	for i in range(4):
		for c, v in zip('xyzw', rows[i]):
			p = getattr(mat.par, 'vec{}value{}'.format(first_block + i, c))
			if p.val != v:
				p.val = v


def update_slots(mb, cam_vp, prev_vp):
	"""slotN ごとに、今と前のフレームの行列を材質に入れ、点が動いている形には前のフレームの形をつなぐ。
	cam_vp・prev_vp：今と前のフレームのカメラの投影 × ビュー（tdu.Matrix）"""
	cur_rows = mat_rows(cam_vp)
	for s in mb.children:
		if not s.name.startswith('slot'):
			continue
		geo, rop = s.storage.get('geo'), s.storage.get('rop')
		if geo is None or not geo.valid or rop is None or not rop.valid:
			continue
		world = geo.worldTransform
		prev_world = s.storage.get('world') or world
		mat = s.op('mat')
		set_rows(mat, 0, mat_rows(world))
		set_rows(mat, 4, cur_rows)
		set_rows(mat, 8, mat_rows(prev_vp * prev_world))
		s.storage['world'] = tdu.Matrix(world)
		# 点が動いているか：元の POP・SOP が前のフレームから計算し直されたか
		cooks = rop.totalCooks
		moving = cooks != s.storage.get('cooks')
		s.storage['cooks'] = cooks
		if moving:
			s.storage['still'] = 0
		else:
			s.storage['still'] = s.storage.get('still', 0) + 1
		# 動き始めたらつなぎ、30 フレーム止まっていたら外す
		want = s.storage['still'] < 30
		add = s.op('prevp')
		src = s.op('prev') if want else s.op('src')
		if add.inputs[1] != src:
			add.inputConnectors[1].connect(src)


# ---------- 毎フレーム

def update(mb):
	st = mb.storage
	frame = absTime.frame
	render = mb.par.Render.eval()
	msg = []
	if render is None:
		msg.append('Render に、ぼかす絵を描いた Render TOP を指定してください')
	if frame % 15 == 0 or 'sig' not in st:
		items, skipped = scene_items(mb, render)
		sig = signature(items)
		if sig != st.get('sig'):
			rebuild_slots(mb, items)
			st['sig'] = sig
		st['ngeo'] = len(items)
		st['skipped'] = skipped

	cam = camera_of(render)
	if cam is not None:
		v = mb.op('velocity')
		vp = view_proj(cam, max(v.width, 1), max(v.height, 1))
		prev = st.get('vp') or vp
		update_slots(mb, vp, prev)
		st['vp'] = tdu.Matrix(vp)
	elif render is not None:
		msg.append('Render TOP の Camera が見つからない')

	if not msg:
		msg.append('形 {} 個'.format(st.get('ngeo', 0)))
		if st.get('skipped'):
			msg.append('描く POP・SOP が無いので飛ばした：' + ', '.join(st['skipped']))
	text = '／'.join(msg)
	if mb.par.Status.eval() != text:
		mb.par.Status.val = text
