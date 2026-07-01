# ============================================================
#  extracter.rpy - 资源导出脚本（兼容 Python 2/3）
#  自动运行：首次生成 export.ini，之后根据 ini 导出到 exported/
#  导出结构：exported/audios/ exported/videos/ exported/images/ 平坦放置
#  图片：ini 不列条目，[all] 下 image + lowestSize(KB) 控制
# ============================================================

init 999 python:
    import os
    import sys
    import shutil

    # -------------------- 配置 --------------------
    AUDIO_EXTS = ('.mp3', '.ogg', '.wav', '.opus', '.flac', '.wma')
    VIDEO_EXTS = ('.webm', '.mp4', '.avi', '.ogv', '.mkv')
    IMAGE_EXTS = ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.tga')
    INI_NAME = 'export.ini'
    EXPORT_DIR_NAME = 'exported'
    AUDIO_DIR_NAME = 'audios'
    VIDEO_DIR_NAME = 'videos'
    IMAGE_DIR_NAME = 'images'

    # -------------------- 辅助函数 --------------------
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

    def _get_basename(file_path):
        return os.path.basename(file_path)

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
            full_path = os.path.join(_get_gamedir(), file_path)
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

    # -------------------- 扫描文件 --------------------
    def _scan_files():
        audio_files = []
        video_files = []
        image_files = []
        seen_sizes = {}

        try:
            all_files = renpy.list_files()
        except:
            all_files = []

        for f in all_files:
            lower_f = f.lower()
            is_audio = lower_f.endswith(AUDIO_EXTS)
            is_video = lower_f.endswith(VIDEO_EXTS)
            is_image = lower_f.endswith(IMAGE_EXTS)
            if not (is_audio or is_video or is_image):
                continue

            size = _get_file_size(f)
            if size in seen_sizes:
                continue
            seen_sizes[size] = f

            if is_audio:
                audio_files.append(f)
            elif is_video:
                video_files.append(f)
            else:
                image_files.append(f)

        return (sorted(audio_files), sorted(video_files), sorted(image_files))

    # -------------------- 生成 ini --------------------
    def _generate_ini(audio_files, video_files, image_files):
        ini_path = _get_ini_path()

        lines = []
        lines.append("; 资源导出配置")
        lines.append("; 将需要导出的条目改为 1，或 [all] 改为 1 导出全部")
        lines.append("; lowestSize: 图片最小文件大小（KB），0 表示全部导出")
        lines.append("")
        lines.append("[all]")
        lines.append("audio = 0")
        lines.append("video = 0")
        lines.append("image = 0")
        lines.append("lowestSize = 0")
        lines.append("")
        lines.append("[音频]")
        for f in audio_files:
            lines.append("%s = 0" % f)
        lines.append("")
        lines.append("[视频]")
        for f in video_files:
            lines.append("%s = 0" % f)
        lines.append("")

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

    # -------------------- 读取 ini --------------------
    def _read_ini():
        ini_path = _get_ini_path()
        if not os.path.exists(ini_path):
            return None

        result = {
            'all': {'audio': '0', 'video': '0', 'image': '0', 'lowestSize': '0'},
            '音频': {},
            '视频': {},
        }
        current_section = None

        try:
            f = open(ini_path, 'rb')
            raw = f.read()
            f.close()

            if sys.version_info[0] >= 3:
                text = raw.decode('utf-8')
            else:
                text = raw

            for line in text.split('\n'):
                line = line.strip()
                if not line or line.startswith(';') or line.startswith('#'):
                    continue

                if line.startswith('[') and line.endswith(']'):
                    section_name = line[1:-1]
                    current_section = section_name if section_name in result else None
                    continue

                if '=' in line and current_section is not None:
                    eq_pos = line.find('=')
                    key = line[:eq_pos].strip()
                    value = line[eq_pos + 1:].strip()

                    if current_section == 'all':
                        if key in ('audio', 'video', 'image', 'lowestSize'):
                            result['all'][key] = value
                    else:
                        result[current_section][key] = value

        except:
            return None

        return result

    # -------------------- 复制文件 --------------------
    def _copy_file(src_path, dst_path):
        try:
            dst_dir = os.path.dirname(dst_path)
            if not os.path.exists(dst_dir):
                os.makedirs(dst_dir)

            try:
                data = renpy.file(src_path).read()
                f = open(dst_path, 'wb')
                f.write(data)
                f.close()
                return True
            except:
                pass

            if os.path.exists(src_path):
                shutil.copy2(src_path, dst_path)
                return True

            game_path = os.path.join(_get_gamedir(), src_path)
            if os.path.exists(game_path):
                shutil.copy2(game_path, dst_path)
                return True

            return False
        except:
            return False

    # -------------------- 获取唯一文件名（重名加 [n]）--------------------
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

    # -------------------- 执行导出 --------------------
    def _do_export(audio_files, video_files, image_files, ini_data):
        export_all_audio = (ini_data['all'].get('audio', '0') == '1')
        export_all_video = (ini_data['all'].get('video', '0') == '1')
        export_all_image = (ini_data['all'].get('image', '0') == '1')

        try:
            lowest_size_kb = int(ini_data['all'].get('lowestSize', '0'))
        except:
            lowest_size_kb = 0

        # KB 转字节
        lowest_size = lowest_size_kb * 1024

        audio_map = ini_data.get('音频', {})
        video_map = ini_data.get('视频', {})

        audio_export_dir = _get_audio_export_dir()
        video_export_dir = _get_video_export_dir()
        image_export_dir = _get_image_export_dir()

        for f in audio_files:
            if export_all_audio or audio_map.get(f, '0') == '1':
                basename = _get_basename(f)
                dst = _get_unique_path(audio_export_dir, basename)
                _copy_file(f, dst)

        for f in video_files:
            if export_all_video or video_map.get(f, '0') == '1':
                basename = _get_basename(f)
                dst = _get_unique_path(video_export_dir, basename)
                _copy_file(f, dst)

        for f in image_files:
            size = _get_file_size(f)
            if size < lowest_size:
                continue
            if export_all_image:
                basename = _get_basename(f)
                dst = _get_unique_path(image_export_dir, basename)
                _copy_file(f, dst)

    # ==================== 自动执行 ====================
    _audio_files, _video_files, _image_files = _scan_files()
    _ini_path = _get_ini_path()

    if not os.path.exists(_ini_path):
        _generate_ini(_audio_files, _video_files, _image_files)
    else:
        _ini_data = _read_ini()
        if _ini_data is not None:
            _do_export(_audio_files, _video_files, _image_files, _ini_data)