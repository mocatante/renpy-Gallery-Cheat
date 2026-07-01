# ============================================================
#  extracter.rpy - 资源导出脚本（兼容 Python 2/3）
#  自动运行：首次生成 export.ini，之后根据 ini 导出
# ============================================================

init 999 python:
    import os
    import sys
    import shutil

    # -------------------- 配置 --------------------
    AUDIO_EXTS = ('.mp3', '.ogg', '.wav', '.opus', '.flac', '.wma')
    VIDEO_EXTS = ('.webm', '.mp4', '.avi', '.ogv', '.mkv')
    INI_NAME = 'export.ini'
    EXPORT_DIR_NAME = 'exported'

    # -------------------- 辅助函数 --------------------
    def _get_gamedir():
        return renpy.config.gamedir

    def _get_ini_path():
        return os.path.join(_get_gamedir(), INI_NAME)

    def _get_export_dir():
        return os.path.join(_get_gamedir(), EXPORT_DIR_NAME)

    def _get_display_name(file_path):
        bn = os.path.basename(file_path)
        no_ext = os.path.splitext(bn)[0]
        return no_ext

    # -------------------- 扫描文件 --------------------
    def _scan_files():
        audio_files = []
        video_files = []
        try:
            for f in renpy.list_files():
                lower_f = f.lower()
                if lower_f.endswith(AUDIO_EXTS):
                    audio_files.append(f)
                elif lower_f.endswith(VIDEO_EXTS):
                    video_files.append(f)
        except:
            pass
        return (sorted(list(set(audio_files))), sorted(list(set(video_files))))

    # -------------------- 生成 ini --------------------
    def _generate_ini(audio_files, video_files):
        ini_path = _get_ini_path()

        lines = []
        lines.append("; 资源导出配置")
        lines.append("; 将需要导出的条目改为 1，或 [all] 改为 1 导出全部")
        lines.append("")
        lines.append("[all]")
        lines.append("audio = 0")
        lines.append("video = 0")
        lines.append("")
        lines.append("[音频]")
        for f in audio_files:
            lines.append("%s = 0" % _get_display_name(f))
        lines.append("")
        lines.append("[视频]")
        for f in video_files:
            lines.append("%s = 0" % _get_display_name(f))
        lines.append("")

        content = "\n".join(lines)

        try:
            # Python 2/3 兼容写文件
            f = open(ini_path, 'wb')
            if sys.version_info[0] >= 3:
                f.write(content.encode('utf-8'))
            else:
                f.write(content)
            f.close()
            return True
        except Exception as e:
            return False

    # -------------------- 读取 ini --------------------
    def _read_ini():
        ini_path = _get_ini_path()
        if not os.path.exists(ini_path):
            return None

        result = {
            'all': {'audio': '0', 'video': '0'},
            '音频': {},
            '视频': {},
        }
        current_section = None

        try:
            # Python 2/3 兼容读文件
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
                        if key in ('audio', 'video'):
                            result['all'][key] = value
                    else:
                        result[current_section][key] = value

        except:
            return None

        return result

    # -------------------- 导出文件 --------------------
    def _copy_file(src_path, dst_path):
        try:
            dst_dir = os.path.dirname(dst_path)
            if not os.path.exists(dst_dir):
                os.makedirs(dst_dir)

            # 尝试 renpy 读取（支持 RPA）
            try:
                data = renpy.file(src_path).read()
                f = open(dst_path, 'wb')
                f.write(data)
                f.close()
                return True
            except:
                pass

            # 回退物理文件
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

    # -------------------- 执行导出 --------------------
    def _do_export(audio_files, video_files, ini_data):
        export_dir = _get_export_dir()
        export_all_audio = (ini_data['all'].get('audio', '0') == '1')
        export_all_video = (ini_data['all'].get('video', '0') == '1')

        audio_map = ini_data.get('音频', {})
        video_map = ini_data.get('视频', {})

        exported = 0

        for f in audio_files:
            display = _get_display_name(f)
            if export_all_audio or audio_map.get(display, '0') == '1':
                dst = os.path.join(export_dir, f)
                if _copy_file(f, dst):
                    exported += 1

        for f in video_files:
            display = _get_display_name(f)
            if export_all_video or video_map.get(display, '0') == '1':
                dst = os.path.join(export_dir, f)
                if _copy_file(f, dst):
                    exported += 1

        return exported

    # ==================== 主程序：自动执行 ====================
    _audio_files, _video_files = _scan_files()
    _ini_path = _get_ini_path()

    if not os.path.exists(_ini_path):
        # 首次运行：生成 ini
        _generate_ini(_audio_files, _video_files)
    else:
        # 非首次：读取 ini 并导出
        _ini_data = _read_ini()
        if _ini_data is not None:
            _do_export(_audio_files, _video_files, _ini_data)