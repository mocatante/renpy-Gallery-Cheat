# ============================================================
#  CG Gallery - 纯净视频版
#  功能：扫描所有视频，前缀仅用于输出过滤，播放使用完整路径
# ============================================================

init 999 python:
    import os

    # -------------------- 配置 --------------------
    GALLERY_CONFIG = {
        # 前缀仅用于输出过滤，不影响扫描和播放
        # 设为空列表或注释掉此键 = 不过滤，全部输出
        'video_prefixes': [],
        'video_exts': ['.webm', '.mp4', '.avi', '.ogv', '.mkv'],
        'output_file': 'gallery_movies.txt',
        'lcp_threshold': 0.7,
    }

    # -------------------- 全局状态 --------------------
    g_gallery_groups = []
    g_gallery_current_group = None
    g_gallery_current_index = 0
    g_gallery_show_button = True
    g_gallery_file_cache = {}

    # -------------------- 文件解析 --------------------
    def _gallery_resolve_file(name):
        """解析文件名 -> (source_type, renderable)。支持完整路径直接解析"""
        if not name:
            return ('missing', None)
        if name in g_gallery_file_cache:
            return g_gallery_file_cache[name]

        cfg = GALLERY_CONFIG

        # 1. 直接尝试 name 作为完整路径（不含扩展名）—— 新格式 txt
        for ext in cfg['video_exts']:
            test_path = name + ext
            if renpy.loadable(test_path):
                movie = Movie(play=test_path, size=(1920, 1080))
                g_gallery_file_cache[name] = ('rpa_movie', movie)
                return g_gallery_file_cache[name]

        # 2. image registry
        if renpy.loadable(name):
            g_gallery_file_cache[name] = ('image', name)
            return g_gallery_file_cache[name]

        # 3. store Movie 对象
        import renpy.store as store
        if hasattr(store, name):
            obj = getattr(store, name)
            if 'Movie' in str(type(obj)) or hasattr(obj, '_play'):
                g_gallery_file_cache[name] = ('movie_obj', obj)
                return g_gallery_file_cache[name]

        # 4. 回退：尝试用前缀拼接（兼容旧格式 txt 或纯 basename）
        for ext in cfg['video_exts']:
            for prefix in cfg.get('video_prefixes', []):
                test_path = prefix + name + ext
                if renpy.loadable(test_path):
                    movie = Movie(play=test_path, size=(1920, 1080))
                    g_gallery_file_cache[name] = ('rpa_movie', movie)
                    return g_gallery_file_cache[name]

        g_gallery_file_cache[name] = ('missing', None)
        return g_gallery_file_cache[name]

    # -------------------- 扫描视频 --------------------
    def _gallery_scan_videos():
        """扫描所有视频文件，返回完整路径列表（不再受前缀限制）"""
        cfg = GALLERY_CONFIG
        videos = []
        try:
            for f in renpy.list_files():
                lower_f = f.lower()
                if any(lower_f.endswith(e) for e in cfg['video_exts']):
                    videos.append(f)
        except:
            pass
        return sorted(list(set(videos)))

    # -------------------- 前缀检查 --------------------
    def _file_matches_prefix(file_path, prefixes):
        """检查文件路径是否匹配任一前缀。prefixes为空则全部匹配"""
        if not prefixes:
            return True
        lower_fp = file_path.lower()
        for p in prefixes:
            if lower_fp.startswith(p):
                return True
        return False

    # -------------------- 分组 --------------------
    def _lcp_length(a, b):
        common = 0
        for i in range(min(len(a), len(b))):
            if a[i] == b[i]:
                common += 1
            else:
                break
        return common

    def _get_bn(fp):
        """获取文件路径的 basename（不含扩展名）"""
        return os.path.splitext(os.path.basename(fp))[0]

    def _auto_group(full_paths):
        """按首单词 + LCP 分组。前缀仅用于输出过滤，不匹配的行会被注释掉"""
        if not full_paths:
            return ""

        cfg = GALLERY_CONFIG
        prefixes = cfg.get('video_prefixes', [])

        # 过滤：只保留匹配前缀的文件用于正式输出（如果前缀列表非空）
        if prefixes:
            valid_paths = [fp for fp in full_paths if _file_matches_prefix(fp, prefixes)]
        else:
            valid_paths = full_paths

        if not valid_paths:
            return ""

        # 按首字符分组（基于 basename）
        by_char = {}
        for fp in valid_paths:
            bn = _get_bn(fp)
            normalized = bn.replace(' ', '_').replace('-', '_')
            char = normalized.split('_')[0].lower()
            by_char.setdefault(char, []).append(fp)

        lines = []
        for char in sorted(by_char.keys()):
            char_files = sorted(by_char[char], key=_get_bn)
            display = char.title()
            lines.append(f"\n# [{display}]")

            # LCP 子分组（基于 basename）
            groups = []
            current = [char_files[0]]
            for i in range(1, len(char_files)):
                prev_bn = _get_bn(char_files[i-1])
                curr_bn = _get_bn(char_files[i])
                common = _lcp_length(prev_bn, curr_bn)
                min_len = min(len(prev_bn), len(curr_bn))
                if common >= min_len * cfg['lcp_threshold'] and common > 0:
                    current.append(char_files[i])
                else:
                    groups.append(current)
                    current = [char_files[i]]
            groups.append(current)

            # All 条目（使用完整路径，不含扩展名）
            all_paths_no_ext = [os.path.splitext(fp)[0] for fp in char_files]
            if len(all_paths_no_ext) > 1:
                lines.append(f'    ("{display} All", ["' + '", "'.join(all_paths_no_ext) + '"]),')

            # 子分组
            for g in groups:
                g_bns = [_get_bn(fp) for fp in g]
                g_paths_no_ext = [os.path.splitext(fp)[0] for fp in g]

                if len(g) == 1:
                    d = g_bns[0].replace('_', ' ').title()
                else:
                    prefix = g_bns[0]
                    for item in g_bns[1:]:
                        prefix = prefix[:_lcp_length(prefix, item)]
                    prefix = prefix.rstrip('_')
                    d = prefix.replace('_', ' ').title() if prefix else g_bns[0].replace('_', ' ').title()

                lines.append(f'    ("{d}", ["' + '", "'.join(g_paths_no_ext) + '"]),')

        # 被过滤的文件在末尾以注释形式输出，供参考/手动启用
        if prefixes:
            excluded = [fp for fp in full_paths if not _file_matches_prefix(fp, prefixes)]
            if excluded:
                lines.append("\n# [未匹配前缀的视频 - 已注释，如需启用请调整前缀配置或取消注释]")
                for fp in excluded:
                    bn = _get_bn(fp)
                    path_no_ext = os.path.splitext(fp)[0]
                    lines.append(f'#    ("{bn.replace("_", " ").title()}", ["{path_no_ext}"]),')

        return '\n'.join(lines)

    # -------------------- 配置持久化 --------------------
    def _gallery_ensure_txt():
        base_dir = os.environ.get('ANDROID_PUBLIC', renpy.config.gamedir) if renpy.android else renpy.config.gamedir
        txt_path = os.path.join(base_dir, GALLERY_CONFIG['output_file'])

        current_videos = _gallery_scan_videos()
        new_content = _auto_group(current_videos)

        old_content = None
        if os.path.exists(txt_path):
            try:
                with open(txt_path, 'r', encoding='utf-8') as f:
                    old_content = f.read()
            except:
                pass

        if old_content == new_content:
            return txt_path

        if not current_videos:
            return txt_path

        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return txt_path

    def _gallery_load():
        txt_path = _gallery_ensure_txt()
        paths = [
            txt_path,
            os.path.join(renpy.config.gamedir, GALLERY_CONFIG['output_file']),
            os.path.join(renpy.config.basedir, "game", GALLERY_CONFIG['output_file']),
            GALLERY_CONFIG['output_file'],
        ]

        content = None
        for p in paths:
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    content = f.read()
                break
            except:
                continue

        if not content:
            return []

        result = []
        for line in content.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            if line.startswith('#'):
                if line.startswith('# [') and line.endswith(']'):
                    result.append({
                        'type': 'header',
                        'display': line[3:-1],
                        'files': [],
                        'is_group': False,
                    })
                continue
            try:
                import ast
                if line.endswith(','):
                    line = line[:-1]
                item = ast.literal_eval(line)
                if isinstance(item, tuple) and len(item) == 2:
                    display, files = item
                    is_group = len(files) > 1
                    result.append({
                        'type': 'item',
                        'display': display + (f"  ({len(files)})" if is_group else ""),
                        'files': list(files),
                        'is_group': is_group,
                    })
            except:
                pass
        return result

    # -------------------- UI 控制 --------------------
    def gallery_open():
        global g_gallery_show_button, g_gallery_groups, g_gallery_file_cache
        g_gallery_show_button = False
        g_gallery_groups = _gallery_load()
        g_gallery_file_cache = {}
        renpy.show_screen("gallery_list")

    def gallery_close():
        global g_gallery_show_button
        g_gallery_show_button = True
        renpy.hide_screen("gallery_list")
        renpy.hide_screen("gallery_player")

    def gallery_play(group_index, file_index=0):
        global g_gallery_current_group, g_gallery_current_index
        g_gallery_current_group = g_gallery_groups[group_index]
        g_gallery_current_index = file_index
        renpy.show_screen("gallery_player")

    def gallery_next():
        global g_gallery_current_index
        if g_gallery_current_group and g_gallery_current_group['is_group']:
            g_gallery_current_index = (g_gallery_current_index + 1) % len(g_gallery_current_group['files'])

    def gallery_prev():
        global g_gallery_current_index
        if g_gallery_current_group and g_gallery_current_group['is_group']:
            g_gallery_current_index = (g_gallery_current_index - 1) % len(g_gallery_current_group['files'])

    # 始终显示悬浮按钮
    try:
        config.always_shown_screens.append("gallery_float_button")
    except:
        pass

# ============================================================
#  Screen - 悬浮按钮
# ============================================================

screen gallery_float_button():
    zorder 100
    if g_gallery_show_button:
        button:
            xalign 0.95 yalign 0.03
            xsize 120 ysize 60
            background Solid("#c0392b")
            hover_background Solid("#e74c3c")
            action Function(gallery_open)
            text "CG":
                xalign 0.5 yalign 0.5
                size 24
                color "#ffffff"
                outlines [(2, "#000000", 0, 0)]

# ============================================================
#  Screen - 画廊列表
# ============================================================

screen gallery_list():
    zorder 200
    modal True
    add Solid("#000000ee")

    text "CGGallery-B站:梦中摩擦忐忑":
        size 36
        color "#ffffff"
        xalign 0.5 ypos 30
        outlines [(2, "#000000", 0, 0)]

    button:
        xalign 0.95 ypos 20
        xsize 80 ysize 60
        background Solid("#00000000")
        action Function(gallery_close)
        text "X":
            xalign 0.5 yalign 0.5
            size 32
            color "#e74c3c"
            outlines [(2, "#000000", 0, 0)]

    viewport:
        xalign 0.5
        ypos 100
        ysize 880
        xsize 720
        scrollbars "vertical"
        mousewheel True
        draggable True

        vbox:
            spacing 2
            for i, group in enumerate(g_gallery_groups):
                if group['type'] == 'header':
                    frame:
                        xsize 700 ysize 40
                        background Solid("#1a5276")
                        text group['display']:
                            size 22
                            color "#f39c12"
                            xalign 0.5 yalign 0.5
                            bold True
                else:
                    button:
                        xsize 700 ysize 50
                        action Function(gallery_play, i, 0)
                        background Solid("#2c3e50")
                        hover_background Solid("#5d6d7e")
                        hbox:
                            xalign 0.5 yalign 0.5
                            spacing 12
                            if group['is_group']:
                                text "▶":
                                    size 20
                                    color "#f39c12"
                                    yalign 0.5
                            else:
                                text "●":
                                    size 16
                                    color "#3498db"
                                    yalign 0.5
                            text group['display']:
                                size 20
                                color "#ecf0f1"
                                yalign 0.5

    $ char_count = len([g for g in g_gallery_groups if g['type'] == 'header'])
    $ item_count = len([g for g in g_gallery_groups if g['type'] == 'item'])
    text f"{char_count} 角色, {item_count} 条目":
        xalign 0.5 yalign 0.98
        size 14
        color "#7f8c8d"

# ============================================================
#  Screen - 视频播放器
# ============================================================

screen gallery_player():
    zorder 300
    modal True

    $ current_group = g_gallery_current_group
    $ current_file = current_group['files'][g_gallery_current_index] if current_group else None
    $ is_group = current_group['is_group'] if current_group else False
    $ current_num = g_gallery_current_index + 1
    $ total_num = len(current_group['files']) if current_group else 0

    python:
        g_gallery_current_what = Solid("#000000")
        if current_file:
            source, obj = _gallery_resolve_file(current_file)
            if source in ('movie_obj', 'rpa_movie'):
                g_gallery_current_what = obj

    add g_gallery_current_what:
        xsize 1920
        ysize 1080
        xalign 0.5
        yalign 0.5

    # 底部控制栏（左侧，减少遮挡）
    frame:
        background Solid("#000000aa")
        xpos 20 yalign 1.0
        xsize 320 ysize 80

        hbox:
            xalign 0.0 yalign 0.5
            spacing 12

            button:
                xsize 80 ysize 50
                background Solid("#c0392b")
                hover_background Solid("#e74c3c")
                action Function(gallery_close)
                text "结束":
                    xalign 0.5 yalign 0.5
                    size 20
                    color "#ffffff"

            if is_group:
                button:
                    xsize 60 ysize 50
                    background Solid("#2980b9")
                    hover_background Solid("#3498db")
                    action Function(gallery_prev)
                    text "◀":
                        xalign 0.5 yalign 0.5
                        size 24
                        color "#ffffff"

                text f"{current_num} / {total_num}":
                    size 20
                    color "#ffffff"
                    yalign 0.5

                button:
                    xsize 60 ysize 50
                    background Solid("#2980b9")
                    hover_background Solid("#3498db")
                    action Function(gallery_next)
                    text "▶":
                        xalign 0.5 yalign 0.5
                        size 24
                        color "#ffffff"

    # 单文件模式：点击画面关闭
    if not is_group:
        button:
            xsize 1920 ysize 1080
            xalign 0.5 yalign 0.0
            action Function(gallery_close)
            background None

    key "K_ESCAPE" action Function(gallery_close)