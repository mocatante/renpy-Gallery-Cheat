# ============================================================
#  extracter.rpy - 资源导出脚本（重构版，兼容 Python 2/3）
#  自动运行：首次生成 export.ini，之后根据 ini 导出到 exported/
#  导出结构：exported/audios/ exported/videos/ exported/images/ 平坦放置
#  文件名去重：ini 只列文件名（无路径），同名不同路径合并为一个条目
#  去重选项：deduplicate = 1 时同名文件按大小去重（仅当大小相同）
#  图片控制：由 [all] 中的 image 开关和 lowestSize（KB）统一控制，不列出具体文件
# ============================================================

init 999 python:
    import os
    import sys
    import shutil

    # -------------------- 配置常量 --------------------
    AUDIO_EXTS = ('.mp3', '.ogg', '.wav', '.opus', '.flac', '.wma')
    VIDEO_EXTS = ('.webm', '.mp4', '.avi', '.ogv', '.mkv')
    IMAGE_EXTS = ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.tga')
    INI_NAME = 'export.ini'
    EXPORT_DIR_NAME = 'exported'
    AUDIO_DIR_NAME = 'audios'
    VIDEO_DIR_NAME = 'videos'
    IMAGE_DIR_NAME = 'images'

    # -------------------- 路径辅助函数 --------------------
    def _get_gamedir():
        return renpy.config.gamedir

    def _get_ini_path():
        return os.path.join(_get_gamedir(), INI_NAME)

    def _get_export_dir():
        return os.path.join(_get_gamedir(), EXPORT_DIR_NAME)

    def _get_audio_export_dir():
        return os.path.join(_get_export_dir(), AUDIO_DIR_NAME)

    def _get_video_export_dir():
        return os.path.join(_get_export_dir(), VIDEO_DIR_NAME)

    def _get_image_export_dir():
        return os.path.join(_get_export_dir(), IMAGE_DIR_NAME)

    # -------------------- 获取文件大小（加强健壮性）--------------------
    def _get_file_size(file_path):
        # 尝试通过 renpy.file 读取
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

        # 尝试从磁盘读取（拼接 gamedir）
        try:
            full_path = os.path.join(_get_gamedir(), file_path)
            if os.path.exists(full_path):
                return os.path.getsize(full_path)
        except:
            pass

        # 尝试直接作为路径
        try:
            if os.path.exists(file_path):
                return os.path.getsize(file_path)
        except:
            pass

        # 最后尝试直接用 open 读取（可能用于绝对路径）
        try:
            with open(file_path, 'rb') as f:
                f.seek(0, 2)
                return f.tell()
        except:
            return -1   # 实在无法获取，返回 -1

    # -------------------- 扫描文件（按类型和文件名分组）--------------------
    def _scan_files_grouped():
        """
        返回结构：
        {
            'audio': { 'basename1': [{'path':..., 'size':...}, ...], ... },
            'video': { ... },
            'image': { ... }
        }
        """
        groups = {'audio': {}, 'video': {}, 'image': {}}
        try:
            all_files = renpy.list_files()
        except:
            all_files = []

        for f in all_files:
            lower_f = f.lower()
            if lower_f.endswith(AUDIO_EXTS):
                typ = 'audio'
            elif lower_f.endswith(VIDEO_EXTS):
                typ = 'video'
            elif lower_f.endswith(IMAGE_EXTS):
                typ = 'image'
            else:
                continue

            size = _get_file_size(f)
            base = os.path.basename(f)
            groups[typ].setdefault(base, []).append({'path': f, 'size': size})

        return groups

    # -------------------- 生成 ini（只包含音频和视频文件名，不列出图片）--------------------
    def _generate_ini(groups):
        ini_path = _get_ini_path()
        lines = []
        lines.append("; 资源导出配置（重构版）")
        lines.append("; deduplicate = 1 表示同名文件按大小去重，仅当大小相同才合并，否则用 [n] 区分")
        lines.append("; 设置为 0 则全部导出，同名文件自动加 [n]")
        lines.append("; [all] 下为全局开关：audio/video/image 控制是否导出该类，lowestSize 为图片最小大小（KB）")
        lines.append("; 音频和视频可在各自 section 中单独开关，图片不列具体文件，由 image 和 lowestSize 统一控制")
        lines.append("")
        lines.append("deduplicate = 1")
        lines.append("")
        lines.append("[all]")
        lines.append("audio = 0")
        lines.append("video = 0")
        lines.append("image = 0")
        lines.append("lowestSize = 0")
        lines.append("")
        # 只写入音频和视频 section，不写入图像
        for section_name, typ in [("音频", "audio"), ("视频", "video")]:
            lines.append("[%s]" % section_name)
            for base in sorted(groups[typ].keys()):
                lines.append("%s = 0" % base)
            lines.append("")
        # 图像 section 不写入，符合要求

        content = "\n".join(lines)
        try:
            f = open(ini_path, 'wb')
            if sys.version_info[0] >= 3:
                f.write(content.encode('utf-8'))
            else:
                f.write(content)
            f.close()
            return True
        except:
            return False

    # -------------------- 读取 ini（解析全局键和节）--------------------
    def _read_ini():
        ini_path = _get_ini_path()
        if not os.path.exists(ini_path):
            return None

        result = {
            'global': {'deduplicate': '1'},   # 默认值
            'all': {'audio': '0', 'video': '0', 'image': '0', 'lowestSize': '0'},
            '音频': {},
            '视频': {},
            # 没有 '图像' 键，因为不列出图片
        }
        current = None

        try:
            f = open(ini_path, 'rb')
            raw = f.read()
            f.close()
            if sys.version_info[0] >= 3:
                text = raw.decode('utf-8')
            else:
                text = raw
        except:
            return None

        for line in text.split('\n'):
            line = line.strip()
            if not line or line.startswith(';') or line.startswith('#'):
                continue

            if line.startswith('[') and line.endswith(']'):
                section = line[1:-1]
                # 只有已知的节才设置，图像节忽略（但我们不期望存在）
                if section in result:
                    current = section
                else:
                    current = None   # 忽略未知节
                continue

            if '=' in line:
                key, val = line.split('=', 1)
                key, val = key.strip(), val.strip()
                if current is None:
                    # 全局键
                    result['global'][key] = val
                else:
                    # 当前节下的键
                    result[current][key] = val

        return result

    # -------------------- 拷贝文件（从 renpy 资源或磁盘）--------------------
    def _copy_file(src_path, dst_path):
        try:
            dst_dir = os.path.dirname(dst_path)
            if not os.path.exists(dst_dir):
                os.makedirs(dst_dir)

            # 尝试 renpy.file
            try:
                data = renpy.file(src_path).read()
                with open(dst_path, 'wb') as f:
                    f.write(data)
                return True
            except:
                pass

            # 尝试从磁盘（gamedir 下）
            game_path = os.path.join(_get_gamedir(), src_path)
            if os.path.exists(game_path):
                shutil.copy2(game_path, dst_path)
                return True

            # 尝试直接作为路径
            if os.path.exists(src_path):
                shutil.copy2(src_path, dst_path)
                return True

            return False
        except:
            return False

    # -------------------- 获取唯一目标路径（自动添加 [n]）--------------------
    def _get_unique_path(base_dir, filename):
        dst_path = os.path.join(base_dir, filename)
        if not os.path.exists(dst_path):
            return dst_path

        name, ext = os.path.splitext(filename)
        n = 1
        while True:
            new_name = "%s[%d]%s" % (name, n, ext)
            dst_path = os.path.join(base_dir, new_name)
            if not os.path.exists(dst_path):
                return dst_path
            n += 1

    # -------------------- 执行导出（根据 ini 配置）--------------------
    def _do_export(groups, ini_data):
        # 读取全局去重开关
        deduplicate = ini_data['global'].get('deduplicate', '1') == '1'

        # 读取 all 开关
        all_audio = ini_data['all'].get('audio', '0') == '1'
        all_video = ini_data['all'].get('video', '0') == '1'
        all_image = ini_data['all'].get('image', '0') == '1'
        # 读取图片最低大小（KB）
        try:
            lowest_size_kb = int(ini_data['all'].get('lowestSize', '0'))
        except:
            lowest_size_kb = 0
        lowest_size = lowest_size_kb * 1024  # 转字节

        # 定义类型处理顺序（图片单独处理）
        # 音频和视频支持具体条目
        type_configs = [
            ('audio', '音频', all_audio, _get_audio_export_dir()),
            ('video', '视频', all_video, _get_video_export_dir()),
        ]

        for typ, section_name, all_flag, export_dir in type_configs:
            section = ini_data.get(section_name, {})
            for base, records in groups[typ].items():
                # 判断是否导出：all 开关或具体条目为 1
                if not (all_flag or section.get(base, '0') == '1'):
                    continue

                # 去重筛选
                if deduplicate:
                    size_map = {}
                    for rec in records:
                        key = rec['size']
                        size_map.setdefault(key, []).append(rec)
                    final_records = [group[0] for group in size_map.values()]
                else:
                    final_records = records

                for rec in final_records:
                    dst = _get_unique_path(export_dir, base)
                    _copy_file(rec['path'], dst)

        # ----- 处理图片（不读取具体条目，只受 all_image 和 lowestSize 控制）-----
        if all_image:
            image_export_dir = _get_image_export_dir()
            for base, records in groups['image'].items():
                # 按大小过滤
                filtered_records = []
                for rec in records:
                    if rec['size'] >= lowest_size or rec['size'] == -1:  # -1 表示未知，默认导出
                        filtered_records.append(rec)
                if not filtered_records:
                    continue

                # 去重筛选
                if deduplicate:
                    size_map = {}
                    for rec in filtered_records:
                        key = rec['size']
                        size_map.setdefault(key, []).append(rec)
                    final_records = [group[0] for group in size_map.values()]
                else:
                    final_records = filtered_records

                for rec in final_records:
                    dst = _get_unique_path(image_export_dir, base)
                    _copy_file(rec['path'], dst)

    # ==================== 自动执行 ====================
    groups = _scan_files_grouped()
    ini_path = _get_ini_path()

    if not os.path.exists(ini_path):
        _generate_ini(groups)
    else:
        ini_data = _read_ini()
        if ini_data is not None:
            _do_export(groups, ini_data)