# -*- coding: utf-8 -*-
"""
截图识字 —— 快捷键截图自动识别文字并复制到剪贴板

用法：
    python app.py
默认快捷键：Ctrl+Win+X（可在界面中录制修改）
"""
import json
import os
import threading
import time
import winsound
import tkinter as tk
from tkinter import ttk, messagebox

import mss
import keyboard
import pyperclip
from PIL import Image, ImageTk, ImageDraw

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(APP_DIR, "config.json")
DEFAULT_CONFIG = {
    "hotkey": "ctrl+windows+x",
    "capture_mode": "region",      # region=框选区域, full=全屏
    "ocr_language": "auto",
}


# ---------------------------------------------------------------------------
# OCR 部分（使用 Windows 系统内置 OCR 引擎，通过 winocr 调用）
# ---------------------------------------------------------------------------
def get_available_ocr_languages():
    """返回系统已安装的 OCR 语言标签列表，如 ['zh-Hans-CN']。"""
    try:
        from winrt.windows.media.ocr import OcrEngine
        return [lang.language_tag for lang in OcrEngine.available_recognizer_languages]
    except Exception:
        return []


def _resolve_language(lang):
    """把 'auto' 或无效标签解析为系统实际支持的 OCR 语言标签。"""
    if lang and lang != "auto":
        try:
            from winrt.windows.globalization import Language
            from winrt.windows.media.ocr import OcrEngine
            if OcrEngine.is_language_supported(Language(lang)):
                return lang
        except Exception:
            pass
    available = get_available_ocr_languages()
    if available:
        return available[0]
    return "zh-Hans-CN"


def _enhance_for_ocr(img):
    """识别前放大图片，提升小字与标点的识别率（对区域截图尤其有效）。"""
    img = img.convert("RGB")
    w, h = img.size
    target = 800          # 最短边目标分辨率
    scale = 1.0
    if min(w, h) < target:
        scale = min(3.0, target / max(1, min(w, h)))
    if scale > 1.0:
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    return img


def _cleanup_text(text):
    """修正常见 OCR 标点误读，尤其适用于复制网址链接的场景。"""
    # 温度符号/全角点/间隔点 → 半角点号（网址中的 '.' 常被误读）
    text = text.replace("℃", ".").replace("．", ".").replace("·", ".")
    if "://" in text:
        import re
        m = re.search(r"https?://[^\s\u4e00-\u9fff]+(?:\s+[^\s\u4e00-\u9fff]+)*", text)
        if m:
            url = m.group(0)
            if len(url.replace(" ", "")) >= max(1, len(text.replace(" ", "")) * 0.7):
                # 整段基本是网址（纯链接场景）：去掉网址内所有被误插的空格
                cleaned = re.sub(r"\s+", "", url)
            else:
                # 混合文本场景：只去掉点号/斜杠/冒号附近的空格
                cleaned = re.sub(r"\s*([.:/])\s*", r"\1", url)
            text = text[:m.start()] + cleaned + text[m.end():]
    return text


def ocr_image(img, lang="auto"):
    """对 PIL 图片执行 OCR，返回识别出的文本（中文/英文均可）。"""
    import asyncio
    try:
        import winocr
    except ImportError:
        raise RuntimeError("未安装 OCR 依赖 winocr，请重新运行「安装.bat」。")
    eff_lang = _resolve_language(lang)
    try:
        res = asyncio.run(winocr.to_coroutine(
            winocr.recognize_pil(_enhance_for_ocr(img), eff_lang)))
    except Exception as e:
        raise RuntimeError(
            "OCR 识别失败：" + str(e) +
            "\n请确认系统安装了 OCR 语言包（设置 -> 时间和语言 -> 语言和区域）。"
        )
    return _cleanup_text((res.text or "").strip())


# ---------------------------------------------------------------------------
# DeepSeek娘 头像（大眼 / 惊讶表情）—— 程序内绘制，无需图片文件、无需联网
# ---------------------------------------------------------------------------
MASCOT_PATH = os.path.join(APP_DIR, "mascot.png")


def draw_mascot(size=200):
    """手绘一只 Q 版 DeepSeek 娘：深海蓝背景 + 大眼闪光 + 惊讶小嘴 + 头顶小鲸鱼发饰。"""
    img = Image.new("RGB", (size, size))
    px = img.load()
    top = (24, 74, 138)
    bottom = (60, 132, 205)
    for y in range(size):
        t = y / max(1, size - 1)
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        for x in range(size):
            px[x, y] = (r, g, b)

    d = ImageDraw.Draw(img, "RGBA")
    cx = size / 2
    fy = size * 0.62
    fr = size * 0.20

    # 头发（深蓝 bob + 后发 + 侧发）
    hc = (26, 42, 74)
    d.ellipse([cx - fr * 1.15, fy - fr * 1.30, cx + fr * 1.15, fy + fr * 1.35], fill=hc)
    d.pieslice([cx - fr * 1.05, fy - fr * 1.50, cx + fr * 1.05, fy + fr * 0.10],
               180, 360, fill=hc)
    d.ellipse([cx - fr * 1.28, fy - fr * 0.50, cx - fr * 0.70, fy + fr * 0.42], fill=hc)
    d.ellipse([cx + fr * 0.70, fy - fr * 0.50, cx + fr * 1.28, fy + fr * 0.42], fill=hc)

    # 脸
    d.ellipse([cx - fr, fy - fr, cx + fr, fy + fr], fill=(255, 230, 214, 255))

    # 大眼（张大眼睛 + 闪光）
    eye_y = fy - fr * 0.15
    eye_r = fr * 0.34
    ex = fr * 0.55
    for sx in (-1, 1):
        exx = cx + sx * ex
        d.ellipse([exx - eye_r, eye_y - eye_r, exx + eye_r, eye_y + eye_r],
                  outline=(40, 50, 80, 255), width=max(2, int(size * 0.01)))
        d.ellipse([exx - eye_r, eye_y - eye_r, exx + eye_r, eye_y + eye_r],
                  fill=(255, 255, 255, 255))
        d.ellipse([exx - eye_r * 0.62, eye_y - eye_r * 0.60,
                   exx + eye_r * 0.62, eye_y + eye_r * 0.66],
                  fill=(47, 109, 255, 255))
        d.ellipse([exx - eye_r * 0.30, eye_y - eye_r * 0.26,
                   exx + eye_r * 0.30, eye_y + eye_r * 0.34],
                  fill=(20, 30, 60, 255))
        # 高光
        d.ellipse([exx - eye_r * 0.28, eye_y - eye_r * 0.42,
                   exx - eye_r * 0.06, eye_y - eye_r * 0.20],
                  fill=(255, 255, 255, 255))
        d.ellipse([exx + eye_r * 0.10, eye_y + eye_r * 0.05,
                   exx + eye_r * 0.26, eye_y + eye_r * 0.22],
                  fill=(255, 255, 255, 255))
    # 上扬眉毛
    for sx in (-1, 1):
        exx = cx + sx * ex
        d.line([exx - eye_r * 0.60, eye_y - eye_r * 1.15,
                exx + eye_r * 0.50, eye_y - eye_r * 0.95],
               fill=(40, 50, 80, 255), width=max(2, int(size * 0.012)))

    # 腮红
    for sx in (-1, 1):
        d.ellipse([cx + sx * fr * 1.15 - fr * 0.14, fy + fr * 0.25 - fr * 0.08,
                   cx + sx * fr * 1.15 + fr * 0.14, fy + fr * 0.25 + fr * 0.08],
                  fill=(255, 160, 180, 120))

    # 惊讶小嘴
    mcx, mcy = cx, fy + fr * 0.42
    d.ellipse([mcx - fr * 0.09, mcy - fr * 0.09, mcx + fr * 0.09, mcy + fr * 0.09],
              fill=(210, 90, 100, 255))

    # 头顶小鲸鱼发饰（DeepSeek 蓝鲸）
    wh_x, wh_y = cx, fy - fr * 1.42
    d.ellipse([wh_x - fr * 0.18, wh_y - fr * 0.12, wh_x + fr * 0.18, wh_y + fr * 0.12],
              fill=(80, 160, 220, 255))
    d.polygon([(wh_x - fr * 0.18, wh_y),
               (wh_x - fr * 0.30, wh_y - fr * 0.12),
               (wh_x - fr * 0.18, wh_y + fr * 0.02)], fill=(80, 160, 220, 255))
    d.polygon([(wh_x + fr * 0.18, wh_y - fr * 0.06),
               (wh_x + fr * 0.28, wh_y - fr * 0.20),
               (wh_x + fr * 0.30, wh_y + fr * 0.02)], fill=(80, 160, 220, 255))
    d.ellipse([wh_x + fr * 0.04, wh_y - fr * 0.04,
               wh_x + fr * 0.12, wh_y + fr * 0.04], fill=(30, 60, 110, 255))

    # 四周闪光星星（衬托“张大眼睛看”）
    import random
    rnd = random.Random(7)
    for _ in range(14):
        sx_ = rnd.uniform(0.10, 0.95) * size
        sy_ = rnd.uniform(0.05, 0.45) * size
        rad = rnd.uniform(2, 5)
        d.line([sx_ - rad, sy_, sx_ + rad, sy_], fill=(255, 255, 255, 200),
               width=max(1, int(size * 0.006)))
        d.line([sx_, sy_ - rad, sx_, sy_ + rad], fill=(255, 255, 255, 200),
               width=max(1, int(size * 0.006)))
    return img


def load_or_draw_mascot():
    """优先使用用户放在同目录的 mascot.png；没有则使用内置手绘头像。"""
    if os.path.exists(MASCOT_PATH):
        try:
            return Image.open(MASCOT_PATH).convert("RGBA")
        except Exception:
            pass
    return draw_mascot(200)


# ---------------------------------------------------------------------------
# 主程序
# ---------------------------------------------------------------------------
class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("截图识字 —— 截图自动复制文字")
        self.root.resizable(False, False)
        self.config = self.load_config()
        self.hotkey_handle = None
        self.tray = None
        self.tray_started = False
        self.available_langs = get_available_ocr_languages()
        self.mascot_img = load_or_draw_mascot()
        self.mascot_photo = None

        self.hotkey_var = tk.StringVar(value=self.config["hotkey"])
        self.status_var = tk.StringVar(value="正在初始化...")
        self.record_btn = None
        self.mode_cb = None
        self.lang_cb = None

        self.build_ui()
        self.register_hotkey()
        self.root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        self.status_var.set(f"就绪 —— 按 {self.config['hotkey']} 截图识别并复制")
        self.start_tray()

    # ---------- 配置 ----------
    @staticmethod
    def load_config():
        cfg = dict(DEFAULT_CONFIG)
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
        return cfg

    def save_config(self):
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showwarning("保存失败", str(e), parent=self.root)

    # ---------- 界面 ----------
    def build_ui(self):
        frame = tk.Frame(self.root, padx=16, pady=16)
        frame.pack(fill="both", expand=True)

        # 头部：DeepSeek娘 大眼头像 + 标题
        header = tk.Frame(frame)
        header.grid(row=0, column=0, columnspan=3, sticky="w")
        self.mascot_photo = ImageTk.PhotoImage(
            self.mascot_img.resize((72, 72), Image.LANCZOS))
        tk.Label(header, image=self.mascot_photo).pack(side="left")
        tk.Label(header, text="截图识字",
                 font=("Microsoft YaHei", 16, "bold")).pack(side="left", padx=(12, 0))
        tk.Label(header, text="按快捷键 → 截图 → 自动复制文字",
                 fg="#888", font=("Microsoft YaHei", 9)).pack(side="left", padx=(12, 0))

        # 快捷键
        tk.Label(frame, text="全局快捷键：", font=("Microsoft YaHei", 11)
                 ).grid(row=1, column=0, sticky="w", pady=(16, 2))
        hotkey_entry = tk.Entry(frame, textvariable=self.hotkey_var, width=18,
                                state="readonly", font=("Consolas", 11))
        hotkey_entry.grid(row=1, column=1, sticky="w")
        self.record_btn = tk.Button(frame, text="🎯 录制快捷键",
                                    command=self.start_record, width=14)
        self.record_btn.grid(row=1, column=2, padx=(8, 0))
        tk.Label(frame, text="按快捷键即可截图，识别到的文字自动复制到剪贴板",
                 fg="#888", font=("Microsoft YaHei", 9)).grid(
            row=2, column=0, columnspan=3, sticky="w", pady=(0, 10))

        # 截图方式
        tk.Label(frame, text="截图方式：", font=("Microsoft YaHei", 11)
                 ).grid(row=3, column=0, sticky="w", pady=4)
        self.mode_cb = ttk.Combobox(frame, values=["框选区域（推荐）", "全屏"],
                                    state="readonly", width=18)
        self.mode_cb.current(0 if self.config["capture_mode"] == "region" else 1)
        self.mode_cb.grid(row=3, column=1, sticky="w")

        # 识别语言
        tk.Label(frame, text="识别语言：", font=("Microsoft YaHei", 11)
                 ).grid(row=4, column=0, sticky="w", pady=4)
        langs = ["auto"] + self.available_langs
        self.lang_cb = ttk.Combobox(frame, values=langs, state="readonly", width=18)
        cur = self.config["ocr_language"]
        self.lang_cb.set(cur if cur in langs else "auto")
        self.lang_cb.grid(row=4, column=1, sticky="w")

        # 状态
        tk.Label(frame, textvariable=self.status_var, fg="#2b579a",
                 font=("Microsoft YaHei", 10), justify="left", wraplength=360,
                 ).grid(row=5, column=0, columnspan=3, sticky="w", pady=(14, 2))

        # 按钮行
        btn_row = tk.Frame(frame)
        btn_row.grid(row=6, column=0, columnspan=3, sticky="w", pady=(8, 0))
        tk.Button(btn_row, text="🔍 测试识别整屏", command=self.test_ocr
                  ).pack(side="left")
        tk.Button(btn_row, text="💾 保存并应用", command=self.save
                  ).pack(side="left", padx=(8, 0))

        tk.Label(frame, text="提示：关闭窗口会最小化到系统托盘，程序常驻后台运行。",
                 fg="#999", font=("Microsoft YaHei", 9)).grid(
            row=7, column=0, columnspan=3, sticky="w", pady=(14, 0))

        tk.Label(frame,
                 text="备注：识别基于系统 OCR，过小的字或个别标点（如 . 与下划线）偶有误差；"
                      "建议框选时尽量放大、只框目标文字。",
                 fg="#b06b00", font=("Microsoft YaHei", 8), justify="left",
                 wraplength=430).grid(
            row=8, column=0, columnspan=3, sticky="w", pady=(4, 0))

    # ---------- 快捷键 ----------
    def register_hotkey(self):
        self.unregister_hotkey()
        combo = self.hotkey_var.get().strip().lower()
        if not combo:
            return
        try:
            self.hotkey_handle = keyboard.add_hotkey(combo, self.on_hotkey,
                                                     suppress=False)
        except Exception as e:
            messagebox.showwarning("快捷键注册失败",
                                   f"无法注册快捷键 “{combo}”:\n{e}",
                                   parent=self.root)

    def unregister_hotkey(self):
        if self.hotkey_handle is not None:
            try:
                keyboard.remove_hotkey(self.hotkey_handle)
            except Exception:
                pass
            self.hotkey_handle = None

    def on_hotkey(self):
        """由 keyboard 的钩子线程回调，派发到后台线程做截图+OCR。"""
        now = time.time()
        if now - getattr(self, "_last_hotkey", 0) < 0.8:   # 防抖
            return
        self._last_hotkey = now
        threading.Thread(target=self.do_ocr_flow, daemon=True).start()

    # ---------- 录制快捷键 ----------
    def start_record(self):
        if self.record_btn:
            self.record_btn.config(text="请按下组合键…", state="disabled")
        threading.Thread(target=self._record_loop, daemon=True).start()

    def _record_loop(self):
        try:
            last = ""
            last_active = time.time()
            start = time.time()
            captured = None
            while time.time() - start < 6:
                combo = keyboard.get_hotkey_name()
                if combo and combo != last:
                    last = combo
                    last_active = time.time()
                if last and time.time() - last_active > 0.5:
                    captured = last
                    break
                time.sleep(0.05)
        except Exception:
            captured = None
        if captured:
            self.root.after(0, lambda: self._set_recorded(captured))
        else:
            self.root.after(0, lambda: self.record_btn.config(
                text="🎯 录制快捷键", state="normal"))

    def _set_recorded(self, combo):
        combo = combo.strip().lower()
        # 若录到的只有修饰键（如 ctrl+windows 而没有功能键），自动补一个字母键
        modifiers = {"ctrl", "alt", "shift", "windows", "win", "cmd", "super"}
        parts = [p for p in combo.split("+") if p]
        if parts and all(p in modifiers for p in parts):
            combo = combo + "+x"
        self.hotkey_var.set(combo)
        self.record_btn.config(text="🎯 录制快捷键", state="normal")
        self.status_var.set(f"已录制快捷键：{combo}，点击「保存并应用」生效")

    # ---------- 截图 ----------
    def capture_region(self, region):
        with mss.mss() as sct:
            shot = sct.grab(region)
            return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")

    def capture_full(self):
        with mss.mss() as sct:
            shot = sct.grab(sct.monitors[0])   # 所有屏幕合成
            return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")

    def do_ocr_flow(self, force_mode=None):
        mode = force_mode or self.config["capture_mode"]
        try:
            if mode == "full":
                img = self.capture_full()
            else:
                sel = threading.Event()
                result_box = {}
                self.root.after(0, lambda: self.do_region_selection(sel, result_box))
                sel.wait()
                region = result_box.get("region")
                if region is None:   # 用户取消
                    self.root.after(0, lambda: self.status_var.set("已取消选择"))
                    return
                img = self.capture_region(region)

            text = ocr_image(img, self.config["ocr_language"])
            if text.strip():
                pyperclip.copy(text)
            self.root.after(0, lambda: self.show_result(text))
        except Exception as e:
            self.root.after(0, lambda: self.show_result("", error=str(e)))

    # ---------- 框选区域 ----------
    def do_region_selection(self, done_event, result_box):
        top = tk.Toplevel(self.root)
        top.attributes("-fullscreen", True)
        top.attributes("-topmost", True)
        top.attributes("-alpha", 0.30)
        top.configure(bg="black")
        canvas = tk.Canvas(top, bg="black", highlightthickness=0, cursor="cross")
        canvas.pack(fill="both", expand=True)
        canvas.create_text(
            top.winfo_screenwidth() / 2, 40,
            text="按住鼠标左键框选要识别的区域，松开确认，Esc 取消",
            fill="white", font=("Microsoft YaHei", 14))
        rect_id = {"id": None}
        start = {}

        def on_press(e):
            start["x"], start["y"] = e.x_root, e.y_root
            if rect_id["id"]:
                canvas.delete(rect_id["id"])
            rect_id["id"] = canvas.create_rectangle(
                e.x_root, e.y_root, e.x_root, e.y_root,
                outline="#ff2d2d", width=2)

        def on_drag(e):
            if rect_id["id"]:
                canvas.coords(rect_id["id"], start["x"], start["y"],
                              e.x_root, e.y_root)

        def finish(region):
            top.destroy()
            result_box["region"] = region
            done_event.set()

        def on_release(e):
            x1, y1 = start.get("x"), start.get("y")
            if x1 is None:
                return
            x2, y2 = e.x_root, e.y_root
            if abs(x2 - x1) < 5 or abs(y2 - y1) < 5:
                finish(None)
                return
            finish({"left": min(x1, x2), "top": min(y1, y2),
                    "width": abs(x2 - x1), "height": abs(y2 - y1)})

        def on_cancel(_):
            finish(None)

        canvas.bind("<ButtonPress-1>", on_press)
        canvas.bind("<B1-Motion>", on_drag)
        canvas.bind("<ButtonRelease-1>", on_release)
        top.bind("<Escape>", on_cancel)
        top.focus_force()

    # ---------- 结果反馈 ----------
    def show_result(self, text, error=""):
        if error:
            self.status_var.set("❌ 识别失败")
            winsound.MessageBeep(winsound.MB_ICONHAND)
            messagebox.showerror("识别失败", error, parent=self.root)
            return
        text = text.strip()
        if text:
            preview = text[:80].replace("\n", " ⏎ ")
            self.status_var.set(f"✅ 已复制到剪贴板：{preview}")
            winsound.MessageBeep(winsound.MB_OK)
            self.show_toast("已复制：" + preview)
        else:
            self.status_var.set("在该区域未识别到文字")
            winsound.MessageBeep()

    def show_toast(self, text):
        try:
            top = tk.Toplevel(self.root)
            top.overrideredirect(True)
            top.attributes("-topmost", True)
            top.attributes("-alpha", 0.92)
            w = self.root.winfo_screenwidth()
            tk.Label(top, text=text, bg="#333333", fg="white",
                     font=("Microsoft YaHei", 11), padx=18, pady=12).pack()
            top.update_idletasks()
            tw, th = top.winfo_reqwidth(), top.winfo_reqheight()
            top.geometry(f"{min(tw, w - 40)}x{th}+{w - min(tw, w - 40) - 24}+60")
            top.after(2500, top.destroy)
        except Exception:
            pass

    # ---------- 按钮动作 ----------
    def test_ocr(self):
        self.status_var.set("正在识别整屏…")
        threading.Thread(target=lambda: self.do_ocr_flow(force_mode="full"),
                         daemon=True).start()

    def save(self):
        self.config["hotkey"] = self.hotkey_var.get().strip().lower()
        self.config["capture_mode"] = "region" if self.mode_cb.current() == 0 else "full"
        self.config["ocr_language"] = self.lang_cb.get()
        self.save_config()
        self.register_hotkey()
        self.status_var.set(f"✅ 设置已保存并生效 —— 按 {self.config['hotkey']} 截图复制文字")

    # ---------- 系统托盘 ----------
    def start_tray(self):
        try:
            import pystray
            icon_img = self.mascot_img.resize((64, 64), Image.LANCZOS)
            menu = pystray.Menu(
                pystray.MenuItem("显示主窗口", self.show_window, default=True),
                pystray.MenuItem("退出", self.quit_app),
            )
            self.tray = pystray.Icon("screenshot_ocr", icon_img, "截图识字", menu)
            self.tray_started = True
            threading.Thread(target=self.tray.run, daemon=True).start()
        except Exception:
            self.tray_started = False

    def show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after(300, lambda: self.root.attributes("-topmost", False))

    def hide_to_tray(self):
        self.root.withdraw()
        if not self.tray_started:
            self.start_tray()

    def quit_app(self):
        self.unregister_hotkey()
        if self.tray:
            try:
                self.tray.stop()
            except Exception:
                pass
        self.root.after(100, self.root.destroy)

    def run(self):
        self.root.mainloop()


def main():
    App().run()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        try:
            with open(os.path.join(APP_DIR, "error.log"), "w", encoding="utf-8") as f:
                traceback.print_exc(file=f)
        except Exception:
            pass
        raise
