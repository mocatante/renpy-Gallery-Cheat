# ============================================================
#  CG Gallery - 纯净视频版（优化分组算法）
#  功能：扫描所有视频，基于去除特殊字符和数字后的公共前缀聚类 + 二次合并
#  生成类似"有分隔符分组效果.txt"的分组结构
#  排序规则：先按原始文件名（含数字），再按去除数字后的文件名
# ============================================================

init -999:
    transform gallery_movie_fit:
        size (1920, 1080)
        xalign 0.5
        yalign 0.5

# 独立的早期注册块：确保即使主 init 块失败，入口仍能显示
# 用 default 声明状态变量，保证 screen 求值时一定存在
default g_gallery_show_button = True
default g_gallery_groups = []
default g_gallery_current_group = None
default g_gallery_current_index = 0
default g_gallery_file_cache = {}
# 注意：g_gallery_photo_cache 不用 default，因为 default 会在"新游戏"时重置为 []，
# 覆盖 _gallery_init() 在 init 阶段扫描的结果。改用 init python 普通变量。

init -2 python:
    # 预注册 movie channel，解决旧版 Ren'Py "Can't register channel outside of init phase" 错误
    # Movie() 在 runtime 创建时需要 channel，channel 只能在 init 阶段注册
    try:
        renpy.audio.music.register_channel("gallery_movie", renpy.config.movie_mixer, loop=True, stop_on_mute=False, movie=True)
    except:
        pass

    # 通用注册方案：用 interact_callbacks 在每次交互时主动 show_screen
    # 不依赖 overlay_screens 机制，不受 suppress_overlay 影响
    # 能在所有 Ren'Py 版本的主菜单/游戏内/游戏菜单都显示入口
    def _gallery_ensure_float_button():
        try:
            if renpy.get_screen("gallery_float_button") is None:
                renpy.show_screen("gallery_float_button")
        except:
            pass

    try:
        if _gallery_ensure_float_button not in config.interact_callbacks:
            config.interact_callbacks.append(_gallery_ensure_float_button)
    except:
        pass

    # 兼容新版 Ren'Py：同时注册 overlay_screens / always_shown_screens（若有）
    # 新版 always_shown_screens 不受 suppress_overlay 影响，优先级更高
    try:
        if "gallery_float_button" not in config.overlay_screens:
            config.overlay_screens.append("gallery_float_button")
    except:
        pass
    try:
        if "gallery_float_button" not in config.always_shown_screens:
            config.always_shown_screens.append("gallery_float_button")
    except:
        pass

init 999 python:
    import os
    import re
    import io
    from collections import defaultdict

    # -------------------- 配置 --------------------
    GALLERY_CONFIG = {
        # 视频文件扩展名
        'video_exts': ['.webm', '.mp4', '.avi', '.ogv', '.mkv'],
        # 图片文件扩展名
        'image_exts': ['.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.tga'],
        # 输出文件路径（相对于 game 目录）
        'output_file': 'gallery_movies.txt',
        # LCP 相似度阈值（0~1），本算法已改用固定最小公共前缀长度3，此参数暂未使用，保留兼容
        'lcp_threshold': 0.7,
        # 父组最少文件数，小于此数的父组整体归入 Others_
        'min_group_size': 2,
        # 视频文件前缀过滤（可选）：只包含这些前缀的文件才会被加入正式输出
        # 设为空列表表示不过滤
        'video_prefixes': [],
    }

    # -------------------- 全局状态 --------------------
    # g_gallery_photo_cache 必须用普通变量（不能用 default），否则"新游戏"时会被重置
    # 其他 UI 状态变量已通过文件顶部的 default 语句声明
    g_gallery_photo_cache = []

    # -------------------- 配置解析 --------------------
    def _gallery_parse_config(content):
        lines = content.strip().split('\n')
        enable = 1
        size = 900

        for line in lines:
            stripped = line.strip()
            if not stripped.startswith('#'):
                break
            cfg = stripped[1:].strip()
            if '=' in cfg:
                eq_pos = cfg.find('=')
                key = cfg[:eq_pos].strip().lower()
                value = cfg[eq_pos + 1:].strip()
                if key == 'enable':
                    try:
                        enable = int(value)
                    except:
                        enable = 0
                elif key == 'size':
                    try:
                        size = int(value)
                    except:
                        size = 900

        return (enable, size)

    # -------------------- 文件解析（保持不变）--------------------
    def _gallery_resolve_file(name):
        """解析文件名 -> (source_type, renderable)"""
        if not name:
            return ('missing', None)
        if name in g_gallery_file_cache:
            return g_gallery_file_cache[name]

        cfg = GALLERY_CONFIG
        # 1. 直接作为完整路径（不含扩展名）
        for ext in cfg['video_exts']:
            test_path = name + ext
            if renpy.loadable(test_path):
                movie = Movie(play=test_path, size=(1920, 1080), channel="gallery_movie")
                g_gallery_file_cache[name] = ('rpa_movie', movie)
                return g_gallery_file_cache[name]

        # 2. 作为图像资源
        if renpy.loadable(name):
            g_gallery_file_cache[name] = ('image', name)
            return g_gallery_file_cache[name]

        # 3. 作为 store 中的 Movie 对象
        import renpy.store as store
        if hasattr(store, name):
            obj = getattr(store, name)
            if 'Movie' in str(type(obj)) or hasattr(obj, '_play'):
                g_gallery_file_cache[name] = ('movie_obj', obj)
                return g_gallery_file_cache[name]

        # 4. 回退：使用前缀拼接
        for ext in cfg['video_exts']:
            for prefix in cfg.get('video_prefixes', []):
                test_path = prefix + name + ext
                if renpy.loadable(test_path):
                    movie = Movie(play=test_path, size=(1920, 1080), channel="gallery_movie")
                    g_gallery_file_cache[name] = ('rpa_movie', movie)
                    return g_gallery_file_cache[name]

        g_gallery_file_cache[name] = ('missing', None)
        return g_gallery_file_cache[name]

    # -------------------- 获取文件大小 --------------------
    def _get_file_size(file_path):
        try:
            fobj = renpy.file(file_path)
            try:
                fobj.seek(0, 2)
                size = fobj.tell()
                fobj.seek(0)
                return size
            except:
                data = fobj.read()
                return len(data)
        except:
            pass

        try:
            full_path = os.path.join(renpy.config.gamedir, file_path)
            if os.path.exists(full_path):
                return os.path.getsize(full_path)
        except:
            pass

        try:
            if os.path.exists(file_path):
                return os.path.getsize(file_path)
        except:
            pass

        return -1

    # -------------------- 扫描视频文件 --------------------
    def _gallery_scan_videos():
        """扫描 game 目录下所有视频文件，返回完整路径列表"""
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

    # -------------------- 扫描图片文件 --------------------
    def _gallery_scan_images(size_kb):
        cfg = GALLERY_CONFIG
        image_exts = tuple(e.lower() for e in cfg['image_exts'])
        images = []
        seen_sizes = {}
        min_size = size_kb * 1024

        try:
            for f in renpy.list_files():
                if f.lower().endswith(image_exts):
                    fsize = _get_file_size(f)
                    if fsize < min_size:
                        continue
                    if fsize in seen_sizes:
                        continue
                    seen_sizes[fsize] = f
                    images.append(f)
        except:
            pass

        return images

    # -------------------- 前缀过滤辅助 --------------------
    def _file_matches_prefix(file_path, prefixes):
        """检查文件路径是否匹配任一前缀（若 prefixes 为空则全部匹配）"""
        if not prefixes:
            return True
        lower_fp = file_path.lower()
        for p in prefixes:
            if lower_fp.startswith(p):
                return True
        return False

    # -------------------- 核心分组算法 --------------------
    def _auto_group(full_paths):
        """
        优化分组算法：
        1. 去除特殊字符（非字母数字下划线转为下划线）
        2. 排序：先按原始文件名（含数字），再按去除数字后的字符串（稳定排序）
        3. 基于去除数字后的字符串的公共前缀长度进行第一次聚类（公共前缀<3则新组）
        4. 公共前缀长度≤2的子组直接归入 Others_
        5. 剩余子组根据第一个单词（下划线前部分）合并为父组
        6. 父组总文件数 < min_group_size 则整个父组归入 Others_
        7. 生成输出格式：# [父组名] 下方为 "父组名 All" 和各个子组条目
        """
        if not full_paths:
            return ""

        cfg = GALLERY_CONFIG
        prefixes = cfg.get('video_prefixes', [])
        min_size = cfg.get('min_group_size', 2)

        # 1. 过滤文件（若配置了前缀）
        if prefixes:
            valid_paths = [fp for fp in full_paths if _file_matches_prefix(fp, prefixes)]
        else:
            valid_paths = full_paths
        if not valid_paths:
            return ""

        # 2. 为每个文件准备元数据
        file_meta = []
        for fp in valid_paths:
            no_ext = os.path.splitext(fp)[0]          # 用于输出的路径（不含扩展名）
            bn = os.path.basename(no_ext)             # 纯文件名（不含目录）
            # 规范化：保留字母、数字、下划线，其他特殊字符转为下划线
            normalized = re.sub(r'[^\w]', '_', bn)
            # 去除数字（用于排序和公共前缀比较）
            no_digits = re.sub(r'\d', '', normalized)
            file_meta.append({
                'path': no_ext,
                'bn': bn,
                'normalized': normalized,
                'no_digits': no_digits,
            })

        # 3. 排序：先按原始文件名（含数字），再按去除数字后的字符串（确保数字顺序优先）
        #   这样 "01_intro" 会排在 "02_intro" 之前，且去除数字后相同的文件会相邻
        file_meta.sort(key=lambda x: (x['normalized'], x['no_digits']))

        # 4. 第一次聚类：基于去除数字后的字符串的公共前缀长度
        subgroups = []          # 每个元素是 [file_meta列表]
        current_group = [file_meta[0]]
        prev_key = file_meta[0]['no_digits']

        for meta in file_meta[1:]:
            cur_key = meta['no_digits']
            # 计算公共前缀长度
            common = 0
            min_len = min(len(prev_key), len(cur_key))
            for i in range(min_len):
                if prev_key[i] == cur_key[i]:
                    common += 1
                else:
                    break
            # 如果公共前缀长度 < 3，则新开一组（视作零散或新主题）
            if common < 3:
                subgroups.append(current_group)
                current_group = [meta]
            else:
                current_group.append(meta)
            prev_key = cur_key
        if current_group:
            subgroups.append(current_group)

        # 5. 为每个子组计算组名（基于原始文件名的公共前缀，保留数字）及去除数字后的公共前缀长度
        subgroup_info = []   # (group_name, file_metas, common_len_no_digits)
        for sg in subgroups:
            if len(sg) == 1:
                # 单文件：组名为其原始 basename
                group_name = sg[0]['bn']
                common_len = len(sg[0]['no_digits'])
            else:
                # 计算原始 basename 的最长公共前缀（保留数字）
                base = sg[0]['bn']
                for meta in sg[1:]:
                    bn = meta['bn']
                    common = 0
                    for i in range(min(len(base), len(bn))):
                        if base[i] == bn[i]:
                            common += 1
                        else:
                            break
                    base = base[:common]
                group_name = base.rstrip('_')
                # 计算去除数字后的公共前缀长度（用于零散判定）
                base_no_digits = sg[0]['no_digits']
                for meta in sg[1:]:
                    nd = meta['no_digits']
                    common = 0
                    for i in range(min(len(base_no_digits), len(nd))):
                        if base_no_digits[i] == nd[i]:
                            common += 1
                        else:
                            break
                    base_no_digits = base_no_digits[:common]
                common_len = len(base_no_digits)
            subgroup_info.append((group_name, sg, common_len))

        # 6. 零散判定：公共前缀长度 <= 2 的子组直接归入 Others_（每个文件单独）
        normal_subgroups = []   # 正常子组，用于二次合并
        others_files = []       # 零散文件（每个文件单独）
        for gname, sg, clen in subgroup_info:
            if clen <= 2:
                # 整个子组视为零散，每个文件单独加入 others
                for meta in sg:
                    others_files.append(meta)
            else:
                normal_subgroups.append((gname, sg))

        # 7. 二次合并：根据子组名的第一个单词（下划线前部分）合并为父组
        parent_dict = defaultdict(list)   # 父组名 -> list of (子组名, 子组文件列表)
        for gname, sg in normal_subgroups:
            # 提取第一个单词（下划线分隔），若无下划线则取整个字符串
            first_word = gname.split('_')[0].lower()
            parent_dict[first_word].append((gname, sg))

        # 8. 决定哪些父组保留，哪些归入 Others_（总文件数 < min_size）
        regular_parents = {}   # 父组名 -> list of (子组名, 子组文件列表)
        for parent, sub_items in parent_dict.items():
            total_files = sum(len(sg) for _, sg in sub_items)
            if total_files >= min_size:
                regular_parents[parent] = sub_items
            else:
                # 整个父组的所有文件拆分为单独文件加入 others
                for _, sg in sub_items:
                    for meta in sg:
                        others_files.append(meta)

        # 9. 生成输出文本
        lines = []

        # 辅助：将下划线字符串转换为标题格式（首字母大写）
        def format_display(s):
            words = s.replace('_', ' ').split()
            return ' '.join(w.capitalize() for w in words)

        # 辅助：生成一个条目行（不使用 f-string）
        def make_entry(display_name, file_metas):
            paths = [m['path'] for m in file_metas]
            # 拼接字符串：'    ("%s", ["%s"]),' % (display_name, '", "'.join(paths))
            return '    ("%s", ["%s"]),' % (display_name, '", "'.join(paths))

        # 处理正常父组
        for parent in sorted(regular_parents.keys()):
            sub_items = regular_parents[parent]
            # 收集本父组所有文件
            all_files = []
            for _, sg in sub_items:
                all_files.extend(sg)
            parent_display = parent.capitalize()
            lines.append("\n# [%s]" % parent_display)
            # All 条目
            # 只有子组数量 > 1 时才生成 All 条目
            if len(sub_items) > 1:
                lines.append(make_entry("%s All" % parent_display, all_files))
            # 各子组条目
            for gname, sg in sub_items:
                display = format_display(gname)
                # 如果子组名与父组名完全相同，添加 "Group" 后缀避免重复
                if display.lower() == parent_display.lower():
                    display = "%s Group" % display
                lines.append(make_entry(display, sg))

        # 处理 Others_ 组
        if others_files:
            lines.append("\n# [Others_]")
            # Others_ All 条目
            lines.append(make_entry("Others_ All", others_files))
            # 每个单独文件作为一个条目
            for meta in others_files:
                display = format_display(meta['bn'])
                lines.append(make_entry(display, [meta]))

        # 若有被前缀过滤掉的文件，以注释输出供参考
        if prefixes:
            excluded = [fp for fp in full_paths if not _file_matches_prefix(fp, prefixes)]
            if excluded:
                lines.append("\n# [未匹配前缀的视频 - 已注释，如需启用请调整前缀配置或取消注释]")
                for fp in excluded:
                    no_ext = os.path.splitext(fp)[0]
                    bn = os.path.basename(no_ext)
                    display = format_display(bn)
                    lines.append('#    ("%s", ["%s"]),' % (display, no_ext))

        return '\n'.join(lines)

    # -------------------- 生成 txt --------------------
    def _gallery_generate_txt(enable, size):
        base_dir = os.environ.get('ANDROID_PUBLIC', renpy.config.gamedir) if renpy.android else renpy.config.gamedir
        txt_path = os.path.join(base_dir, GALLERY_CONFIG['output_file'])

        videos = _gallery_scan_videos()
        video_content = _auto_group(videos)

        config_header = "# enable = %s\n# size = %s\n" % (enable, size)
        new_content = config_header + video_content

        with io.open(txt_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        return txt_path

    # -------------------- 启动时初始化 --------------------
    def _gallery_init():
        global g_gallery_photo_cache

        base_dir = os.environ.get('ANDROID_PUBLIC', renpy.config.gamedir) if renpy.android else renpy.config.gamedir
        txt_path = os.path.join(base_dir, GALLERY_CONFIG['output_file'])

        if os.path.exists(txt_path):
            try:
                with io.open(txt_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                enable, size = _gallery_parse_config(content)
                if enable == 1:
                    g_gallery_photo_cache = _gallery_scan_images(size)
            except:
                pass
        else:
            _gallery_generate_txt(1, 900)
            g_gallery_photo_cache = _gallery_scan_images(900)

    # -------------------- 加载菜单数据 --------------------
    def _gallery_load():
        base_dir = os.environ.get('ANDROID_PUBLIC', renpy.config.gamedir) if renpy.android else renpy.config.gamedir
        txt_path = os.path.join(base_dir, GALLERY_CONFIG['output_file'])
        paths = [
            txt_path,
            os.path.join(renpy.config.gamedir, GALLERY_CONFIG['output_file']),
            os.path.join(renpy.config.basedir, "game", GALLERY_CONFIG['output_file']),
            GALLERY_CONFIG['output_file'],
        ]

        content = None
        for p in paths:
            try:
                with io.open(p, 'r', encoding='utf-8') as f:
                    content = f.read()
                break
            except:
                continue

        if not content:
            return []

        enable, size = _gallery_parse_config(content)

        result = []
        for line in content.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            if line.startswith('# enable') or line.startswith('# size'):
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
                    if is_group:
                        display = display + "  (%d)" % len(files)
                    result.append({
                        'type': 'item',
                        'display': display,
                        'files': list(files),
                        'is_group': is_group,
                    })
            except:
                pass

        if enable == 1 and g_gallery_photo_cache:
            result.append({
                'type': 'header',
                'display': 'Photoes_',
                'files': [],
                'is_group': False,
            })
            result.append({
                'type': 'item',
                'display': 'Photoes_ All  (%d)' % len(g_gallery_photo_cache),
                'files': g_gallery_photo_cache,
                'is_group': True,
            })

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
        global g_gallery_current_index, g_gallery_current_group
        if not g_gallery_current_group:
            return
        files = g_gallery_current_group["files"]
        if len(files) <= 1:
            return
        g_gallery_current_index = (g_gallery_current_index + 1) % len(files)
        renpy.restart_interaction()

    def gallery_prev():
        global g_gallery_current_index, g_gallery_current_group
        if not g_gallery_current_group:
            return
        files = g_gallery_current_group["files"]
        if len(files) <= 1:
            return
        g_gallery_current_index = (g_gallery_current_index - 1) % len(files)
        renpy.restart_interaction()

    # 将悬浮按钮设为始终显示
    # 注意：注册逻辑已移至文件顶部的 init -2 python: 块，确保独立执行
    # 旧版 Ren'Py 只有 config.overlay_screens，没有 config.always_shown_screens

    # ==================== 启动时执行 ====================
    _gallery_init()

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

    text "CG Gallery - B站:梦中摩擦忐忑":
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
    # 不使用 f-string，改用字符串拼接
    text str(char_count) + " 角色, " + str(item_count) + " 条目":
        xalign 0.5 yalign 0.98
        size 14
        color "#7f8c8d"

# ============================================================
#  Screen - 视频/图片播放器
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
            elif source == 'image':
                g_gallery_current_what = obj

    add g_gallery_current_what at gallery_movie_fit

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

                # 不使用 f-string
                text str(current_num) + " / " + str(total_num):
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

    key "K_LCTRL" action Function(gallery_next)
    key "K_RCTRL" action Function(gallery_next)