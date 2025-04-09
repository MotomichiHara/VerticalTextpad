import tkinter as tk
from tkinter import filedialog, font, ttk, simpledialog, messagebox
import os
import platform
import re
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
import numpy as np
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors

# 高DPIスケーリングを有効化
try:
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

class VerticalNotepad:
    def __init__(self, root):
        self.root = root
        self.root.title("TateX")
        self.root.geometry("600x800")

        self.current_font = font.Font(family="HiraKakuProN-W3", size=20)
        #自動改行
        self.indent_on_newline = tk.BooleanVar(value=False) 
        self.check_kakko_mismatch = tk.BooleanVar(value=False)

        #テーマ変更用
        self.theme = tk.StringVar(value="Light")
        self.text_color = "black"
        self.caret_color="black"

        
        # ボタンのスタイル設定
        self.style = ttk.Style()
        self.style.configure("RoundedButton.TButton", borderwidth=0, relief="flat", padding=6, background="#e0e0e0", foreground="black")
        self.style.map("RoundedButton.TButton", background=[("active", "#c0c0c0")])
        #スクロールバーのスタイル設定
        self.style.theme_use("clam")
        self.style.configure("Vertical.TScrollbar", gripcount=0, troughcolor="#f0f0f0", background="#e0e0e0")
        self.style.map("Vertical.TScrollbar", background=[("active", "#c0c0c0")])

        self.canvas = tk.Canvas(self.root, bg="white")
        self.canvas.pack(fill="both", expand=True)

        #横方向スクロール
        self.scrollbar_x = ttk.Scrollbar(self.root, orient="horizontal", command=self.canvas.xview)
        self.scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.configure(xscrollcommand=self.scrollbar_x.set)

        #縦方向スクロール?
        # self.scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.canvas.yview)
        # self.scrollbar.pack(side="right", fill="y")
        # self.canvas.configure(yscrollcommand=self.scrollbar.set)


        self.canvas.bind("<Configure>", self.redraw)
        self.canvas.bind("<Key>", self.on_key_press)
        self.canvas.bind("<Button-1>", self.on_mouse_click)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)  # ドラッグイベントを追加
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_release)  # リリースイベントを追加
        self.canvas.bind("<MouseWheel>", self.on_mousewheel) 
        self.canvas.focus_set()

        self.text = ""
        self.kakko_stack = []
        self.caret_pos = 0

        
        self.create_menu()
        self.create_status_bar()
        self.apply_theme()
    
        self.search_results = []
        self.search_index = 0
        self.highlighted_ranges = []

        self.selected_text_start = None
        self.selected_text_end = None
        self.drag_start_pos = None  # ドラッグ開始位置を保持

        self.auto_indent = []

        self.search_term = ""
        self.replace_term = ""
        self.search_window_open = False
        self.search_index = 0
        self.key_pressed = False

    def on_kakko_mismatch_change(self): #コールバック関数の追加
        self.redraw()

    def create_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="ファイル", menu=file_menu)
        file_menu.add_command(label="新規 (Ctrl+N)", command=self.new_file, accelerator="Ctrl+N")
        file_menu.add_command(label="開く (Ctrl+O)", command=self.open_file, accelerator="Ctrl+O")  # 開くを追加
        file_menu.add_command(label="保存 (Ctrl+S)", command=self.save_file, accelerator="Ctrl+S")
        file_menu.add_command(label="PDF出力", command=self.export_to_pdf)
        file_menu.add_command(label="終了 (Ctrl+Q)", command=self.root.quit, accelerator="Ctrl+Q")

        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="編集", menu=edit_menu)
        edit_menu.add_command(label="コピー (Ctrl+C)", command=self.copy_text, accelerator="Ctrl+C")
        edit_menu.add_command(label="貼り付け (Ctrl+V)", command=self.paste_text, accelerator="Ctrl+V")
        edit_menu.add_command(label="切り取り (Ctrl+X)", command=self.cut_text, accelerator="Ctrl+X")
        edit_menu.add_command(label="検索・置換 (Ctrl+F)", command=self.search_text, accelerator="Ctrl+F")

        format_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="書式", menu=format_menu)
        format_menu.add_command(label="フォント変更", command=self.change_font)
        format_menu.add_checkbutton(label="自動字下げ", variable=self.indent_on_newline)
        format_menu.add_checkbutton(label="括弧不一致チェック", variable=self.check_kakko_mismatch, command=self.on_kakko_mismatch_change)
        format_menu.add_command(label="テーマ変更", command=self.change_theme)

        self.root.bind("<Control-n>", lambda e: self.new_file())
        self.root.bind("<Control-o>", lambda e: self.open_file())  # Ctrl+Oのショートカットを追加
        self.root.bind("<Control-s>", lambda e: self.save_file())
        self.root.bind("<Control-q>", lambda e: self.root.quit())
        self.root.bind("<Control-f>", lambda e: self.search_text())
        self.root.bind("<Control-h>", lambda e: self.replace_text())
        self.root.bind("<Control-c>", lambda e: self.copy_text())
        self.root.bind("<Control-v>", lambda e: self.paste_text())

    def create_status_bar(self):
        self.status_bar = tk.Label(self.root, text="", bd=1, relief=tk.SUNKEN, anchor=tk.W, bg="#e0e0e0", padx=5)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    # def update_status_bar(self):
    #     char_count = len(self.text)
    #     line_count = self.text.count("\n") + 1
    #     x, y = self.get_caret_coords(self.caret_pos)
    #     self.status_bar.config(text=f"文字数: {char_count}, 行数: {line_count}")

    def count_characters(self):
        char_count = len(self.text)
        line_count = self.calculate_line_count()
        self.status_bar.config(text=f"文字数: {char_count}, 行数: {line_count}")

    def calculate_line_count(self):
        width = self.canvas.winfo_width()
        line_height = self.current_font.metrics("linespace")
        char_width = self.current_font.measure("あ")
        x = width - char_width
        y = line_height
        line_count = 1
        for char in self.text:
            if char == "\n":
                line_count += 1
                y = line_height
                x -= char_width * 1.5
            else:
                y += line_height
                if y > self.canvas.winfo_height() - line_height:
                    line_count += 1
                    y = line_height
                    x -= char_width * 1.5
        return line_count

    def new_file(self):
        self.text = ""
        self.caret_pos = 0
        self.redraw()
        self.highlighted_ranges = []
        self.selected_text_start = None
        self.selected_text_end = None

    def get_current_line_number(self):
        width = self.canvas.winfo_width()
        line_height = self.current_font.metrics("linespace")
        char_width = self.current_font.measure("あ")
        x = width - char_width
        y = line_height
        line_number = 1
        char_index = 0

        for char in self.text:
            if char_index == self.caret_pos:
                return line_number
            if char == "\n":
                line_number += 1
                y = line_height
                x -= char_width * 1.5
            else:
                y += line_height
                if y > self.canvas.winfo_height() - line_height:
                    line_number += 1
                    y = line_height
                    x -= char_width * 1.5
            char_index += 1

        return line_number

    def save_file(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".txt",
                                               filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(self.text)

    def open_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    self.text = f.read()
                self.caret_pos = 0
                self.redraw()
                self.highlighted_ranges = []
                self.selected_text_start = None
                self.selected_text_end = None
            except Exception as e:
                messagebox.showerror("エラー", f"ファイルを開く際にエラーが発生しました:\n{e}")

    def change_font(self):
        def apply_new_font(new_font):
            self.current_font = new_font
            self.redraw()

        FontDialog(self.root, self.current_font, apply_new_font)
    
    def change_theme(self):
        themes = ["Light", "Dark","優しい", "原稿用紙風","原稿用紙風-優しい","Matrix"]
        def apply_new_theme(new_theme):
            self.theme.set(new_theme)
            self.apply_theme()
            self.redraw()

        ThemeDialog(self.root, self.theme.get(), apply_new_theme, themes)

    def apply_theme(self):
        if self.theme.get() == "Dark":
            self.root.config(bg="gray12")
            self.canvas.config(bg="gray12")
            self.status_bar.config(bg="gray20", fg="white")
            self.text_color = "white"
            self.caret_color="white"
            self.canvas.update()
        elif self.theme.get() == "優しい":
            self.root.config(bg="ivory")
            self.canvas.config(bg="ivory")
            self.status_bar.config(bg="ivory", fg="ivory")
            self.text_color = "gray"
            self.caret_color="gray"
            self.canvas.update()
        elif self.theme.get() == "原稿用紙風":
            self.root.config(bg="#f8f8f8")  # 薄いグレーの背景
            self.canvas.config(bg="#f8f8f8")
            self.status_bar.config(bg="#e0e0e0", fg="black")
            self.text_color = "black"
            self.caret_color = "black"
            self.canvas.update()
        elif self.theme.get() == "Matrix":
            self.root.config(bg="black")
            self.canvas.config(bg="black")
            self.status_bar.config(bg="#003300", fg="#00FF00")
            self.text_color = "#00FF00"  # マトリックス風の緑色
            self.caret_color = "#00FF00"
            self.canvas.update()
        elif self.theme.get() == "原稿用紙風-優しい":
            self.root.config(bg="ivory")  # 薄いグレーの背景
            self.canvas.config(bg="ivory")
            self.status_bar.config(bg="SystemButtonFace", fg="black")
            self.text_color = "black"
            self.caret_color = "black"
            self.canvas.update()
        else:
            self.root.config(bg="white")
            self.canvas.config(bg="white")
            self.status_bar.config(bg="SystemButtonFace", fg="black")
            self.canvas.itemconfig("text", fill="black")
            self.text_color = "black"
            self.caret_color="black"
            self.canvas.update()
        
    def is_caret_at_last_line(self):
        current_line = self.get_current_line_number()
        total_lines = self.calculate_line_count()
        return current_line == total_lines

    def redraw(self, event=None):
        self.canvas.delete("all")
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()

        line_height = self.current_font.metrics("linespace")
        char_width = self.current_font.measure("あ")
        x = width-char_width
        y = line_height


        rotate_chars = "「『（【《」』）】》―ー"

        last_char = ""
        char_index = 0
        count_return = 0

        max_x = width
        #原稿用紙風テーマに設定時のみ
        if self.theme.get() == "原稿用紙風":
            self.draw_genkou_yoshi_background(width, height, char_width, line_height , max_x, "#a52a2a")

        if self.theme.get() == "原稿用紙風-優しい":
            self.draw_genkou_yoshi_background(width, height, char_width, line_height , max_x, "#a52a2a")
        
        self.kakko_stack.clear()
        for char in self.text:
            kakko_error_positions = []
            if char == "「":
                self.kakko_stack.append("」")
            elif char == "『":
                self.kakko_stack.append("』")
            elif char == "（":
                self.kakko_stack.append("）")
            elif char == "【":
                self.kakko_stack.append("】")
            elif char == "《":
                self.kakko_stack.append("》")
            elif char == "[":
                self.kakko_stack.append("]")
            if char in "」』）】》]":
                if len(self.kakko_stack) > 0 and self.kakko_stack[len(self.kakko_stack) - 1] == char:
                    del self.kakko_stack[len(self.kakko_stack) - 1]
                else:
                    kakko_error_positions.append(char_index)

            if char_index in kakko_error_positions and self.check_kakko_mismatch.get():
                self.canvas.create_rectangle(
                x - char_width // 2, y, x + char_width // 2, y + line_height,
                fill="red",  # 赤色のマーカー
                outline=""
                )
            #原稿用紙風テーマ無限に線が引けるけど重くなる
            # if self.theme.get() == "原稿用紙風":
            #     self.draw_genkou_yoshi_background(width, height, char_width, line_height , max_x)
            if char == "\n":
                #if self.indent_on_newline.get() and last_char == ".":
                #    self.text = self.text[:char_index + 1] + " " + self.text[char_index + 1:]
                #y = line_height
                #x -= char_width * 1.5
                #char_index += 1
                #continue
                if char_index == self.caret_pos and char_index < len(self.text):
                    caret_x = x
                    caret_y = y
                    self.canvas.create_line(caret_x - char_width // 2, caret_y -line_height/2 + 2, caret_x + char_width // 2, caret_y -line_height/2 + 2, fill=self.caret_color)
                if self.auto_indent[count_return]: #機能がONかOFFか
                    y = line_height*2
                    x -= char_width * 1.5  
                else:
                    y = line_height
                    x -= char_width * 1.5
                char_index += 1
                count_return += 1
                continue
            last_char = char
            

            offset_x = 0
            offset_y = 0
            angle = 0

            if char in rotate_chars:
                angle = -90
                offset_x = char_width // 4
                offset_y = line_height // 4
            elif char in "、。":
                offset_x = char_width // 2
                offset_y = -line_height // 4

            if char in "「『（［｛":
                offset_y = -line_height // 4
                offset_x = char_width // 4
            elif char in "」』）］｝":
                offset_y = line_height // 4
                offset_x = -char_width // 4

            # 選択範囲のハイライト表示
            if self.selected_text_start is not None and self.selected_text_end is not None:
                if self.selected_text_start <= char_index < self.selected_text_end:
                    self.canvas.create_rectangle(x - char_width // 2, y- line_height/2, x + char_width // 2, y + line_height/2, fill="lightblue", outline="")

            for i, (start, end) in enumerate(self.highlighted_ranges):
                if start <= char_index < end:
                    if i == self.search_index and self.search_results:
                        self.canvas.create_rectangle(x - char_width // 2, y- line_height/2, x + char_width // 2, y + line_height/2, fill="yellow", outline="")
                    else:
                        self.canvas.create_rectangle(x - char_width // 2, y- line_height/2, x + char_width // 2, y + line_height/2, fill="#ffee99", outline="")

            self.canvas.create_text(
                x + offset_x, y + offset_y,
                text=char,
                font=self.current_font,
                anchor="center",
                angle=angle,
                fill=self.text_color, 
            )

            if char_index == self.caret_pos:
                caret_x = x
                caret_y = y
                self.canvas.create_line(caret_x - char_width // 2, caret_y-line_height/2 + 2, caret_x + char_width // 2, caret_y - line_height / 2 + 2 , fill=self.caret_color)

            y += line_height
            #if y > height - line_height:
            #    self.text = self.text[:char_index] + "\n" + self.text[char_index:]
            #    self.caret_pos += 1
            #    return self.redraw()
            if y > height - line_height:
                y = line_height
                x -= char_width * 1.5
            max_x = min(max_x, x)
            char_index += 1

        if self.caret_pos == len(self.text):
            caret_x = x
            caret_y = y
            self.canvas.create_line(caret_x - char_width // 2, caret_y -line_height/2 + 2, caret_x + char_width // 2, caret_y -line_height/2 + 2, fill=self.caret_color)

        self.canvas.configure(scrollregion=(max_x - width*2, 0, width, self.canvas.bbox("all")[3]))
        self.count_characters()
    

    def draw_genkou_yoshi_background(self, width, height, char_width, line_height , max_x,color):
         # 罫線の間隔を計算
        char_width = self.current_font.measure("あ")
        vertical_line_spacing = self.current_font.measure("あ") * 1.5
        line_height = self.current_font.metrics("linespace")
        # 罫線の色
        line_color = color
        ## 縦線を描画
        start_x = width -char_width+ vertical_line_spacing/2
        if max_x >= 0 :
            left_limit = max_x - width*4
        else:
            left_limit = max_x * 10 - width*4
        while start_x > left_limit:
            # 1本目の縦線を描画
            self.canvas.create_line(start_x - 1, 0, start_x - 1, height, fill=line_color)
            # 2本目の縦線を描画
            self.canvas.create_line(start_x + 1, 0, start_x + 1, height, fill=line_color)
            start_x -= vertical_line_spacing
        # 横線を描画
        start_y = line_height/2
        while start_y < height :
            self.canvas.create_line(left_limit, start_y, width, start_y, fill=line_color, dash=(2, 2))
            start_y += line_height


    def pdf_draw_genkou_yoshi_background(self, canvas_obj, width, height, char_width, line_height, max_x, color):
        # 罫線の間隔を計算
        vertical_line_spacing = char_width * 1.5
        # 罫線の色
        line_color =  colors.HexColor("#a52a2a")
        ## 縦線を描画
        start_x = width
        if max_x >= 0:
            left_limit = max_x - width * 4
        else:
            left_limit = max_x * 10 - width * 4

        while start_x > left_limit:
            canvas_obj.setStrokeColor(line_color)
            # 1本目の縦線を描画
            canvas_obj.line(start_x - 1, 0, start_x - 1, height-line_height-line_height/2)
            # 2本目の縦線を描画
            canvas_obj.line(start_x + 1, 0, start_x + 1, height-line_height- line_height/2)
            start_x -= vertical_line_spacing
        
        # #上二重線
        canvas_obj.line(left_limit, height-line_height-line_height/2 +1, width, height-line_height-line_height/2 +1 )
        canvas_obj.line(left_limit, height-line_height-line_height/2 -1, width, height-line_height-line_height/2 -1 )
        # #下二重線
        canvas_obj.line(left_limit, 2, width, 2 )
        canvas_obj.line(left_limit, 1, width, 1 )
        # 横線を描画
        start_y = 0 
        while start_y < height- line_height*2 :
            canvas_obj.setStrokeColor(line_color)
            canvas_obj.setDash(2, 2)
            canvas_obj.line(left_limit, start_y, width, start_y)
            start_y += line_height
        



    def on_key_press(self, event):
        if event.keysym in ("Left", "Right", "Up", "Down"):
            self.move_caret(event.keysym)
        elif event.keysym == "Return":
            newline_index = self.text[:self.caret_pos].count("\n")
            if self.indent_on_newline.get():
                self.auto_indent.insert(newline_index, True)
            else:
                self.auto_indent.insert(newline_index, False)
            self.text = self.text[:self.caret_pos] + "\n" + self.text[self.caret_pos:]
            self.caret_pos += 1
        elif event.keysym == "space":
            self.text = self.text[:self.caret_pos] + "\u3000" + self.text[self.caret_pos:]
            self.caret_pos += 1
        elif event.char and (event.char.isprintable() or event.char == "\u3000"):
            self.text = self.text[:self.caret_pos] + event.char + self.text[self.caret_pos:]
            self.caret_pos += 1
            self.key_pressed = True
        elif event.keysym == "BackSpace" and self.caret_pos > 0:
            if self.text[self.caret_pos - 1] == "\n": #改行を削除するなら
                newline_index = self.text[:self.caret_pos].count("\n")
                del self.auto_indent[newline_index - 1]
            self.text = self.text[:self.caret_pos - 1] + self.text[self.caret_pos:]
            self.caret_pos -= 1
        elif event.keysym == "Delete" and self.caret_pos < len(self.text):
            if self.text[self.caret_pos] == "\n": #改行を削除するなら
                newline_index = self.text[:self.caret_pos].count("\n")
                del self.auto_indent[newline_index - 1]
            self.text = self.text[:self.caret_pos] + self.text[self.caret_pos + 1:]
        self.redraw()
        if self.search_window_open:
            self.perform_search()

    def move_caret(self, direction):
        line_height = self.current_font.metrics("linespace")
        char_width = self.current_font.measure("あ")
        x, y = self.get_caret_coords(self.caret_pos)
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        begin_x = width-char_width
        begin_y = line_height

        pass_new = False

        if direction == "Up":
            if not self.caret_pos == 0:
                if self.text[self.caret_pos - 1] == "\n" and not self.caret_pos == 1 and not self.text[self.caret_pos - 2] == "\n":
                    x, y = self.get_caret_coords(self.caret_pos - 1)
                elif self.text[self.caret_pos - 1] == "\n" and not self.caret_pos == 1 and self.text[self.caret_pos - 2] == "\n":
                    x += char_width * 1.5
                else:
                    x, y = self.get_caret_coords(self.caret_pos - 1)
            #y -= line_height
        elif direction == "Down":
            #y += line_height
            if not self.caret_pos == len(self.text):
                if self.text[self.caret_pos] == "\n" and not self.caret_pos == len(self.text) - 1 and not self.text[self.caret_pos + 1] == "\n":
                    x, y = self.get_caret_coords(self.caret_pos + 1)
                elif self.text[self.caret_pos] == "\n" and not self.caret_pos == len(self.text) - 1 and self.text[self.caret_pos + 1] == "\n":
                    x -= char_width * 1.5
                    y = line_height
                else:
                    x, y = self.get_caret_coords(self.caret_pos + 1)
        elif direction == "Left":
            if self.is_caret_at_last_line():
                self.caret_pos = len(self.text)
                pass_new = True
            else:
                x -= char_width * 1.5
                new_pos = self.get_char_index_from_coords(x, y)
                if not self.caret_pos == len(self.text) and new_pos == len(self.text):
                    pass_new = True
                    if self.text[self.caret_pos] == "\n":
                        if self.text[self.caret_pos + 1] == "\n":
                            self.caret_pos += 1
                        else:
                            self.caret_pos += 1
                            while not self.text[self.caret_pos] == "\n":
                                self.caret_pos += 1
                    else:
                        while not self.text[self.caret_pos] == "\n":
                            self.caret_pos += 1
                        if self.text[self.caret_pos] == "\n":
                            self.caret_pos += 1
                        while not self.text[self.caret_pos] == "\n":
                            self.caret_pos += 1


        elif direction == "Right":
            if self.get_current_line_number() == 1:
                x = begin_x
                y = begin_y
            else:
                x += char_width * 1.5
                new_pos = self.get_char_index_from_coords(x,y)
                if new_pos == len(self.text):
                    pass_new = True
                    self.caret_pos -= 1
                    while not self.text[self.caret_pos] == "\n":
                        self.caret_pos -= 1
            


            

        # 新しいカーソル位置を計算
        if not pass_new:
            new_pos = self.get_char_index_from_coords(x, y)
            if 0 <= new_pos <= len(self.text):
                self.caret_pos = new_pos

        self.redraw()

    def get_caret_coords(self, pos):
        line_height = self.current_font.metrics("linespace")
        char_width = self.current_font.measure("あ")
        x = self.canvas.winfo_width() - char_width
        y = line_height
        char_index = 0
        count_return_get_char = 0
        for char in self.text:
            if char_index == pos:
                return x, y
            if char == "\n":
                if self.auto_indent[count_return_get_char]:
                    y = line_height * 2
                    x -= char_width * 1.5
                else:
                    y = line_height
                    x -= char_width * 1.5
            else:
                y += line_height
                if y > self.canvas.winfo_height() - line_height:
                    y = line_height
                    x -= char_width * 1.5
            char_index += 1
        return x, y

    def on_mouse_click(self, event):
        self.key_pressed = True
        self.drag_start_pos = self.mouse_get_char_index_from_coords(event.x, event.y)
        self.caret_pos = self.drag_start_pos
        self.selected_text_start = self.caret_pos
        self.selected_text_end = self.caret_pos
        self.redraw()

    def on_mouse_drag(self, event):
        if self.drag_start_pos is not None:
            current_pos = self.mouse_get_char_index_from_coords(event.x, event.y)
            self.caret_pos = current_pos
            self.selected_text_start = min(self.drag_start_pos, current_pos)
            self.selected_text_end = max(self.drag_start_pos, current_pos)
            self.redraw()

    def on_mouse_release(self, event):
        self.drag_start_pos = None

    def on_mousewheel(self, event):
        if event.delta:
            self.canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")

    def get_char_index_from_coords(self, x, y):
        line_height = self.current_font.metrics("linespace")
        char_width = self.current_font.measure("あ")
        start_x = self.canvas.winfo_width() - char_width
        start_y = line_height
        char_index = 0

        count_return_get_char = 0

        for char in self.text:
            #if x >= start_x - char_width // 2 and x <= start_x + char_width // 2 and y >= start_y and y <= start_y + line_height:
            if start_x == x and start_y == y:
                return char_index
            if char == "\n":
                if self.auto_indent[count_return_get_char]:
                    start_y = line_height * 2
                    start_x -= char_width * 1.5
                else:
                    start_y = line_height
                    start_x -= char_width * 1.5
            else:
                start_y += line_height
                if start_y > self.canvas.winfo_height() - line_height:
                    start_y = line_height
                    start_x -= char_width * 1.5
            char_index += 1
        return len(self.text)
    
    def mouse_get_char_index_from_coords(self, x, y):
        line_height = self.current_font.metrics("linespace")
        char_width = self.current_font.measure("あ")
        height=self.canvas.winfo_height()
        start_x = self.canvas.winfo_width() - char_width
        start_y = line_height
        char_index = 0

        count_return_get_char = 0

        for char in self.text:
            if x >= start_x - char_width // 2 and x <= start_x + char_width // 2 and y >= start_y-line_height and y <= start_y :
            # if start_x == x and start_y == y:
                return char_index
            # if x >= start_x - char_width // 2 and x <= start_x + char_width // 2 and y >= height-line_height and y <= height:
            #     return char_index
            if char == "\n":
                if self.auto_indent[count_return_get_char]:
                    start_y = line_height * 2
                    start_x -= char_width * 1.5
                else:
                    start_y = line_height
                    start_x -= char_width * 1.5
            else:
                start_y += line_height
                if start_y > self.canvas.winfo_height() - line_height:
                    start_y = line_height
                    start_x -= char_width * 1.5
            char_index += 1

            # 最後の行をクリックした場合、次の行の先頭の文字のインデックスを返す
            if x >= start_x+char_width*1.5 - char_width // 2 and x <= start_x +char_width*1.5+ char_width // 2 and y >= height - last_y and y <= height:
                return char_index
            last_y = start_y

        return len(self.text)

    def search_text(self):
        #search_term = simpledialog.askstring("検索", "検索文字列を入力してください (正規表現可):")
        def on_search_change(name, index, mode):
            self.search_term = search_var.get()
            self.perform_search()
            update_search_status()

        def on_replace_change(name, index, mode):
            self.replace_term = replace_var.get()

        def on_search_window_destroy(event):
            self.highlighted_ranges = []
            self.redraw()
            self.search_window_open = False
        def next_search_result():
            if self.search_results:
                self.search_index = (self.search_index + 1) % len(self.search_results)
                self.caret_pos = self.search_results[self.search_index]
                self.redraw()
                update_search_status()

        def prev_search_result():
            if self.search_results:
                self.search_index = (self.search_index - 1) % len(self.search_results)
                self.caret_pos = self.search_results[self.search_index]
                self.redraw()
                update_search_status()
        
        def replace_current():
            if self.search_term and self.replace_term and self.search_results:
                start = self.search_results[self.search_index]
                end = start + len(re.search(self.search_term, self.text[start:]).group())
                self.text = self.text[:start] + self.replace_term + self.text[end:]
                self.caret_pos = start + len(self.replace_term)
                self.redraw()
                self.perform_search()
                update_search_status()

        def replace_all():
            if self.search_term and self.replace_term:
                try:
                    self.text, replace_count = re.subn(self.search_term, self.replace_term, self.text)
                    self.redraw()
                    self.perform_search()
                    update_search_status()
                except re.error as e:
                    messagebox.showerror("正規表現エラー", f"無効な正規表現です: {e}")

        def update_search_status():
            if self.search_results:
                status_label.config(text=f"{self.search_index + 1}/{len(self.search_results)}件")
            else:
                status_label.config(text="0件")

        search_window = tk.Toplevel(self.root)
        search_window.title("検索") # ウィンドウの名前を変更
        tk.Label(search_window, text="検索文字列を入力してください (正規表現可):").pack(padx=10, pady=5) # ラベルを追加
        search_var = tk.StringVar()
        search_entry = tk.Entry(search_window, textvariable=search_var)
        search_entry.pack(padx=10, pady=10)
        search_entry.focus_set()
        search_var.trace_add("write", on_search_change)

        tk.Label(search_window, text="置換文字列:").pack(padx=10, pady=5)
        replace_var = tk.StringVar()
        replace_entry = tk.Entry(search_window, textvariable=replace_var)
        replace_entry.pack(padx=10, pady=5)
        replace_var.trace_add("write", on_replace_change)

        button_frame = tk.Frame(search_window)
        button_frame.pack(padx=10, pady=5)

        prev_button = tk.Button(button_frame, text="<", command=prev_search_result)
        prev_button.pack(side=tk.LEFT)

        status_label = tk.Label(button_frame, text="0件")
        status_label.pack(side=tk.LEFT)

        next_button = tk.Button(button_frame, text=">", command=next_search_result)
        next_button.pack(side=tk.LEFT)

        replace_button = tk.Button(button_frame, text="置換", command=replace_current)
        replace_button.pack(side=tk.LEFT)

        replace_all_button = tk.Button(button_frame, text="全置換", command=replace_all)
        replace_all_button.pack(side=tk.LEFT)

        self.search_window_open = True
        search_window.bind("<Destroy>", on_search_window_destroy)
    
    def perform_search(self):
        if self.search_term:
            try:
                self.search_results = [m.start() for m in re.finditer(self.search_term, self.text)]
                self.search_index = 0
                self.highlighted_ranges = []
                if self.search_results:
                    if not self.key_pressed:
                        self.caret_pos = self.search_results[0]
                    else:
                        self.key_pressed = False
                    for start_pos in self.search_results:
                        self.highlighted_ranges.append((start_pos, start_pos + len(re.search(self.search_term, self.text[start_pos:]).group())))
                    self.redraw()
                else:
                    self.highlighted_ranges = []
                    self.redraw()
            except re.error as e:
                self.highlighted_ranges = [] # 検索文字列が空の場合はハイライト表示をクリア
                self.redraw()
        else:
            self.highlighted_ranges = []
            self.redraw()

    def export_to_pdf(self):
                # フォントを登録
        font_path = f"C:/TaTeX/LINESeedJP_A_TTF_Rg.ttf"
        
        # フォントファイルのパスを指定

        if not os.path.exists(font_path):
            messagebox.showerror("エラー", f"フォントファイルが見つかりません: {font_path}")
            return
        try:
            pdfmetrics.registerFont(TTFont("BIZ", font_path))
        except Exception as e:
            messagebox.showerror("エラー", f"フォント登録中にエラーが発生しました: {e}")
            return
        file_path = filedialog.asksaveasfilename(defaultextension=".pdf",
                                               filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")])
        if file_path:
            c = canvas.Canvas(file_path, pagesize=A4)
            width, height = A4
            line_height = self.current_font.metrics("linespace")
            char_width = self.current_font.measure("あ")
            x = width-char_width 
            y = height 
            char_index = 0
            count_return = 0
            rotate_chars = "「『（【《」』）】》―ー"
            page_char_count = 0

            # def set_pdf_font(canvas_obj, font_family, font_size):
            #         font_path = self.current_font.actual().get("file")
            #         if font_path and os.path.exists(font_path):
            #             try:
            #                 pdfmetrics.registerFont(TTFont(font_family, font_path))
            #                 canvas_obj.setFont(font_family, font_size)
            #                 return
            #             except Exception as e:
            #                 print(f"Error registering font: {e}")
            #         canvas_obj.setFont("Helvetica", font_size)
            #         print(f"Using default font (Helvetica) for {font_family}")
            # set_pdf_font(c, self.current_font.actual()["family"], self.current_font.actual()["size"])

            # 背景色と文字の色を設定
            background_color = colors.white  # デフォルトの背景色
            text_color = colors.black  # デフォルトの文字色
            c.setFont('BIZ', self.current_font.actual()["size"] )

            if self.theme.get() == "Dark":
                background_color = colors.gray12
                text_color = colors.white
            elif self.theme.get() == "優しい":
                background_color = colors.ivory
                text_color = colors.gray
            elif self.theme.get() == "原稿用紙風":
                background_color = colors.HexColor("#f8f8f8")
                text_color = colors.black
            elif self.theme.get() == "原稿用紙風-優しい":
                background_color = colors.ivory
                text_color = colors.black
            elif self.theme.get() == "Matrix":
                background_color = colors.black
                text_color =  colors.HexColor("#00FF00")           


            # 背景色を設定
            c.setFillColor(background_color)
            c.rect(0, 0, width, height, fill=1)
            if self.theme.get() in ["原稿用紙風", "原稿用紙風-優しい"]:
                self.pdf_draw_genkou_yoshi_background(c, width, height, char_width, line_height, width, colors.red)

            count_return_pdf = 0
            for char in self.text:
                if char_index == 0:
                    y = height - line_height
                if char == "\n":
                    if self.auto_indent[count_return_pdf]: #機能がONかOFFか
                        y = height - line_height*2
                        x -= char_width * 1.5
                        char_index += 1    
                    else:
                        y = height - line_height
                        x -= char_width * 1.5
                        char_index += 1
                    count_return_pdf += 1
                    continue
                #if char == "\n":
                #    #y = height-line_height 
                #    y = line_height
                #    x -= char_width
                #    char_index += 1   
                #    continue

                offset_x = 0
                offset_y = 0
                angle = 0
                if char in rotate_chars:
                    angle=-90
                    offset_x = char_width//4
                    offset_y = line_height//4 
                elif char in "、。":
                    offset_x = char_width // 2
                    offset_y = -line_height // 4
                elif char in "「『（［｛":
                    offset_y = -line_height // 4
                elif char in "」』）］｝":
                    offset_y = line_height // 4

                offset_x *= mm
                offset_y *= mm

                y -= line_height 
                if y < 0 :
                    y = height-line_height * 2
                    x -= char_width * 1.5 
                x -= char_width
                if x < 0:
                    c.showPage()  # 新しいページを作成
                    # set_pdf_font(c, self.current_font.actual()["family"], self.current_font.actual()["size"])
                    c.setFillColor(background_color)
                    c.setFillColor(background_color)
                    c.rect(0, 0, width, height, fill=1)
                    if self.theme.get() in ["原稿用紙風", "原稿用紙風-優しい"]:
                        self.pdf_draw_genkou_yoshi_background(c, width, height, char_width, line_height, width, colors.red)
                    x = width - char_width  # x座標を右端に戻す
                    y = height - line_height * 2 #y座標を初期化
                else:
                    x += char_width
                c.saveState()
                c.translate(x + offset_x, y + offset_y)
                c.rotate(angle)
                c.setFillColor(text_color) 
                c.drawString(0, 0, char)
                c.restoreState()

                
                char_index+=1
                page_char_count += 1


            c.save()
            messagebox.showinfo("PDF出力", "PDFファイルを出力しました。")

    def copy_text(self):
        if self.selected_text_start is not None and self.selected_text_end is not None:
            selected_text = self.text[self.selected_text_start:self.selected_text_end]
            self.root.clipboard_clear()
            self.root.clipboard_append(selected_text)
    
    def cut_text(self):
        if self.selected_text_start is not None and self.selected_text_end is not None:
            selected_text = self.text[self.selected_text_start:self.selected_text_end]
            self.root.clipboard_clear()
            self.root.clipboard_append(selected_text)
            self.text = self.text[:self.selected_text_start] + self.text[self.selected_text_end:]
            self.caret_pos = self.selected_text_start
            self.selected_text_start = None
            self.selected_text_end = None
            self.redraw()

    def paste_text(self):
        pasted_text = self.root.clipboard_get()
        self.text = self.text[:self.caret_pos] + pasted_text + self.text[self.caret_pos:]
        self.caret_pos += len(pasted_text)
        self.redraw()

class FontDialog(tk.Toplevel):
    def __init__(self, parent, current_font, apply_callback):
        super().__init__(parent)
        self.title("フォント選択")
        self.transient(parent)
        self.result = None
        self.apply_callback = apply_callback

        tk.Label(self, text="フォント:").grid(row=0, column=0, padx=5, pady=5)
        self.font_var = tk.StringVar(value=current_font.actual()["family"])

        # フォントリストから"@"が付いているフォントを除外
        font_names = [f for f in font.families() if not f.startswith("@")]
        self.font_combo = ttk.Combobox(self, textvariable=self.font_var, values=font_names)
        self.font_combo.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(self, text="サイズ:").grid(row=1, column=0, padx=5, pady=5)
        self.size_var = tk.IntVar(value=current_font.actual()["size"])
        self.size_combo = ttk.Combobox(self, textvariable=self.size_var, values=[12, 14, 16, 18, 20, 24, 28, 32])
        self.size_combo.grid(row=1, column=1, padx=5, pady=5)

        tk.Button(self, text="OK", command=self.on_ok).grid(row=2, column=0, pady=10)
        tk.Button(self, text="キャンセル", command=self.destroy).grid(row=2, column=1, pady=10)

        self.grab_set()
        self.geometry(f"+{parent.winfo_x() + 50}+{parent.winfo_y() + 50}")

    def on_ok(self):
        selected_font = self.font_var.get()
        selected_size = self.size_var.get()

        if selected_font and selected_size:
            self.result = font.Font(family=selected_font, size=selected_size)
            self.apply_callback(self.result)

        self.destroy()

class ThemeDialog(tk.Toplevel):
    def __init__(self, parent, current_theme, apply_callback, themes):
        super().__init__(parent)
        self.title("テーマ選択")
        self.transient(parent)
        self.apply_callback = apply_callback
        self.theme_var = tk.StringVar(value=current_theme)

        tk.Label(self, text="テーマ:").grid(row=0, column=0, padx=5, pady=5)
        self.theme_combo = ttk.Combobox(self, textvariable=self.theme_var, values=themes)
        self.theme_combo.grid(row=0, column=1, padx=5, pady=5)

        tk.Button(self, text="OK", command=self.on_ok).grid(row=1, column=0, pady=10)
        tk.Button(self, text="キャンセル", command=self.destroy).grid(row=1, column=1, pady=10)

        self.grab_set()
        self.geometry(f"+{parent.winfo_x() + 50}+{parent.winfo_y() + 50}")

    def on_ok(self):
        selected_theme = self.theme_var.get()
        self.apply_callback(selected_theme)
        self.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = VerticalNotepad(root)
    root.mainloop()