from traceback import format_exception_only
import numpy as np
import copy
import os
import csv
import datetime
import cv2

import getopt
import sys


usage = '''form.py usage:

python form.py <options>
        --user=<number> / -u <number> : 参加者番号 1~
        --trial_num=<number> / -t <number> : 全試行数
        --start=<number> / -s <number> : startする試行番号 (default : 1)
        --gain=<float> / -g <float> : フォームのサイズ（default : 1）
        --zmean=<0 or 1> / -z <0 or 1> : 7段階尺度を(0)0～6にするか(1)-3～3にするか（default : 1）
        --debug / -d : シートパラメータの設定
'''

f_resource = "./resources/"
conf_filename = f_resource + "form_conf.csv"
sheet_filename = f_resource + "sheet.png"
f_result = "./result/"
result_prename = f_result + "result"
result_etcname = ".csv"


##################################
## sheet parameter
##################################

# トグルボタン
class Button:
    def __init__(self, center_x, center_y, width, height, text="", margin_gain=1.0):
        self.cx = center_x
        self.cy = center_y
        self.minx = (int)(center_x - width / 2 + 0.5)
        self.maxx = (int)(center_x + width / 2 + 0.5)
        self.miny = (int)(center_y - height / 2 + 0.5)
        self.maxy = (int)(center_y + height / 2 + 0.5)
        self.state = False
        self.text = text
        # ボタン中心からどれだけ離れた範囲をクリック領域とみなすか
        self.margin_gain = margin_gain
        self.marginx = (int)(width / 2 * self.margin_gain + 0.5) 
        self.marginy = (int)(height / 2 * self.margin_gain + 0.5)

    def State(self):
        return self.state
    
    def SetState(self, state):
        self.state = state

    # 戻り値：ステータス変更！
    def UpdateState(self, x, y):
        if not self.IsClick(x, y):
            return False 
        self.state = not self.state
        return True
    
    def IsClick(self, x, y):
        if x < self.cx - self.marginx or x > self.cx + self.marginx or y < self.cy - self.marginy or y > self.cy + self.marginy:
            return False
        else:
            return True

    def Render(self, target_img, on_color = (0, 0, 255), off_color = (255, 255, 255), border_color = (0, 0, 0), text_color = (0, 0, 0)):
        color = on_color if self.state else off_color
        cv2.rectangle(target_img, (self.minx, self.miny), (self.maxx, self.maxy), color, thickness=-1)
        cv2.rectangle(target_img, (self.minx, self.miny), (self.maxx, self.maxy), border_color)
        if self.text == "":
            return
        (w, h), baseline = cv2.getTextSize(self.text, cv2.FONT_HERSHEY_SIMPLEX, 1, 1)
        x1 = (int)(self.cx - w / 2 + 0.5)
        y1 = (int)(self.cy + h / 5 + 0.5)
        cv2.putText(target_img, self.text, (x1, y1), cv2.FONT_HERSHEY_SIMPLEX, 1, text_color, 2)

    def RenderMarginArea(self, target_img, color = (0, 255, 255)):
        cv2.rectangle(target_img, (self.cx - self.marginx, self.cy - self.marginy), 
                    (self.cx + self.marginx, self.cy + self.marginy), color, thickness=-1)


# グループボタン、どれか一個しかONにならない
class RadioButton:
    # buttons : class Button
    def __init__(self, buttons):
        self.num = len(buttons)
        self.buttons = [b for b in buttons]

    def SetAllFalse(self):
        for b in self.buttons:
            b.SetState(False)
            
    def UpdateState(self, x, y):
        for b in self.buttons:
            # ボタンのステートが変われば
            if b.UpdateState(x, y):
                now_state = b.State()
                self.SetAllFalse()
                b.SetState(now_state)

    # -1 : All False, 0 ~ num-1 : buttons[xx] is True
    def State(self):
        ret_val = None
        for i, b in enumerate(self.buttons):
            if b.State():
                ret_val = i
        return ret_val

    def Render(self, target_img, on_color = (0, 0, 255), off_color = (255, 255, 255), border_color = (0, 0, 0), text_color=(0, 0, 0)):
        for b in self.buttons:
            b.Render(target_img, on_color, off_color, border_color, text_color)

    def RenderMarginArea(self, target_img, color = (0, 255, 255)):
        for b in self.buttons:
            b.RenderMarginArea(target_img, color)


# フォーム
class Form:
    def __init__(self, back_img, window_name, trial_num, size=1.0):
        f = lambda a:(int)(a * size + 0.5)

        if not os.path.isfile(conf_filename):
            print(f"{conf_filename}がありません")
            sys.exit()
        with open(conf_filename, "r") as z:
            reader = csv.reader(z)
            dummy = [row for row in reader]
            imgw = (int)(dummy[0][0])
            imgh = (int)(dummy[0][1])
            t = {"l":(int)(dummy[1][0]), "t":(int)(dummy[1][1]), "r":(int)(dummy[1][2]), "b":(int)(dummy[1][3])}
            p = {"cx":(int)(dummy[2][0]), "cy":(int)(dummy[2][1]), "w":(int)(dummy[2][2]), "h":(int)(dummy[2][3])}
            n = {"cx":(int)(dummy[3][0]), "cy":(int)(dummy[3][1]), "w":(int)(dummy[3][2]), "h":(int)(dummy[3][3])}
            g = [{"cx1":(int)(row[0]), "cx2":(int)(row[1]), "cy":(int)(row[2]), "w":(int)(row[3]), "h":(int)(row[4]), "n":(int)(row[5])} for row in dummy[4:]]

        self.form_width = f(imgw)
        self.form_height = f(imgh)

        self.img = copy.deepcopy(back_img)
        self.img = cv2.resize(self.img, (self.form_width, self.form_height))
        self.window_name = window_name
        cv2.namedWindow(self.window_name)
        cv2.moveWindow(self.window_name, 0, 0)

        # 画面に条件数を書く
        # 条件の枠を消す
        cv2.rectangle(self.img, (f(t['l']), f(t['t'])), (f(t['r']) + 2, f(t['b']) + 2), (255, 255, 255), -1)
        # 数字を描画
        fsize = f(t['b'] - t['t']) / 24
        (w, h), base = cv2.getTextSize(str(trial_num), cv2.FONT_HERSHEY_SIMPLEX, fsize, 2)
        cv2.putText(self.img, str(trial_num), (f(t['l']), f(t['t']) + h), cv2.FONT_HERSHEY_SIMPLEX, fsize, (0, 0, 0), 2)

        # Prevボタン
        self.prev_button = Button(f(p['cx']), f(p['cy']), f(p['w']), f(p['h']), "prev")
        # Nextボタン
        self.next_button = Button(f(n['cx']), f(n['cy']), f(n['w']), f(n['h']), "next")

        self.all_questions = []
        idx = 0
        for idx in range(len(g)):
            # Question idx+1
            buttons_num = g[idx]["n"]   # ボタンの数
            buttons_width = f(g[idx]["w"])
            buttons_height = f(g[idx]["h"])    
            q_yc = f(g[idx]["cy"])          
            q_xmin = f(g[idx]["cx1"])
            q_xmax = f(g[idx]["cx2"]) 
            q_xcs = [int(q_xmin + i * (q_xmax - q_xmin) / (buttons_num - 1) + 0.5) for i in range(buttons_num)]
            buttons = []
            for i in range(buttons_num):
                buttons.append(Button(q_xcs[i], q_yc, buttons_width, buttons_height, margin_gain=2.4))
            self.all_questions.append(RadioButton(buttons))

    def Update(self, x, y):
        can_push_next = True
        for question in self.all_questions:
            question.UpdateState(x, y)
            if question.State() == None:
                can_push_next = False
        self.prev_button.UpdateState(x, y)
        if can_push_next:
            self.next_button.UpdateState(x, y)

    def RenderAll(self, x, y):
        tmp = copy.deepcopy(self.img)
        can_push_next = True
        for question in self.all_questions:
            question.Render(tmp)
            if question.State() == None:
                can_push_next = False
        self.prev_button.Render(tmp)
        text_color = (0, 0, 0) if can_push_next else (230, 230, 230) 
        self.next_button.Render(tmp, text_color=text_color)
        # カーソルの描画
        cv2.circle(tmp, (x, y), 5, (0, 255, 255), thickness=-1)
        cv2.imshow(self.window_name, tmp)
        return cv2.waitKey(3)
    
    def IsGotoPrevState(self):
        return self.prev_button.State()

    def IsGotoNextState(self):
        return self.next_button.State()
    
    def GetData(self, is_normalize = True):
        row = {}
        for i, question in enumerate(self.all_questions):
            bias = 0 if not is_normalize else (int)((question.num - 1) / 2 + 0.5)
            row[f'q{i+1}'] = question.State() - bias
        return row, len(self.all_questions)

    def SetMouseEvent(self, func):
        # マウスイベント時に関数mouse_touch_flagの処理を行う
        cv2.setMouseCallback(self.window_name, func)


global _x
global _y
global _touch_flag
_x = 500
_y = 500
_touch_flag = False

# マウスイベント
def __mouse_event(event, x, y, flag, params):
    global _x
    global _y
    global _touch_flag
    _x = x
    _y = y
    if event == cv2.EVENT_LBUTTONDOWN:
        _touch_flag = True


def __find_nearest_black_pixel(img, cx, cy, ret_type, margin):
    top = cy
    bot = cy
    left = cx
    right = cx
    while img[top,cx, 0] > 250:
        top -= 1
    top = top - margin
    while img[bot, cx, 0] > 250:
        bot += 1
    bot = bot + margin
    while img[cy, left, 0] > 250:
        left -= 1
    left = left - margin
    while img[cy, right, 0] > 250:
        right += 1
    right = right + margin
    if ret_type == "lrtb":
        return left, right, top, bot
    if ret_type == "cxcywh":
        wid = right - left
        hei = bot - top
        return (int)(left + wid / 2 + 0.5), (int)(top + hei / 2 + 0.5), wid, hei

# (x1,y)から(x2,y)までの横プロファイルで、黒線が何本あるかを導出し、ボタンの数を計算する
def __calculate_button_num(img, x1, x2, y, margin):
    x = x1
    black_line_num = 0
    while x < x2:
        # 白画素の場合
        if img[y, x, 0] > 250:
            x += 1
        # 黒画素の場合
        else:
            black_line_num += 1
            x += margin + 1  # margin分だけ先を見る
    return (int)(black_line_num / 2) + 1   # ボタンの数

def FindFormParameter():
    global _x
    global _y
    global _touch_flag
    img = cv2.imread(sheet_filename)
    width = img.shape[1]
    height = img.shape[0]

    # 終了ボタンの描画
    thx = 25
    thy = 25
    cv2.rectangle(img, (0, 0), (thx, thy), (255, 255, 0))


    click_infos = []    # クリックした情報を格納する場所
    q = 1   # 質問番号
    exit_flag = False
    while not exit_flag:
        enable_exit = False   # To exitが有効かどうか
        i = len(click_infos)
        if i == 0:
            window_name = "Click the area that shows 'trial_number'"
        elif i == 1:
            window_name = "Click 'prev button area'"
        elif i == 2:
            window_name = "Click 'next button area'"
        elif ((i - 3) % 2) == 0:
            window_name = f"Click Q{q}'s leftest button. [To exit] Click the skybox in the upper left."
            enable_exit = True
        else:
            window_name = f"Click Q{q}'s rightest button."

        cv2.namedWindow(window_name)
        cv2.namedWindow(window_name)
        cv2.moveWindow(window_name, 0, 0)
        cv2.setMouseCallback(window_name, __mouse_event)
        while True:
            bar_img = img.copy()
            cv2.circle(bar_img, (_x, _y), 5, (0, 255, 0), -1)
            cv2.imshow(window_name, bar_img)
            if _touch_flag:
                if _x < thx and _y < thy and enable_exit:
                    exit_flag = True
                    break
                click_infos.append([_x, _y])
                cv2.circle(img, (_x, _y), 5, (0, 0, 255), -1)
                _touch_flag = False
                break
            cv2.waitKey(5)
        cv2.destroyWindow(window_name)

    if len(click_infos) < 5 or len(click_infos) % 2 == 0:
        print("clicks is something wrong")
        return 

    # クリックした情報からデコードする        
    img = cv2.imread(sheet_filename)

    margin = 3

    # 番号を描画するエリア
    x, y = click_infos[0]
    left, right, top, bot = __find_nearest_black_pixel(img, x, y, "lrtb", margin)
    title_area = [left, top, right, bot]

    # prevボタンを描画するエリア
    x, y = click_infos[1]
    cx, cy, wid, hei = __find_nearest_black_pixel(img, x, y, "cxcywh", margin)
    prev_area = [cx, cy, wid, hei]

    # nextボタンを描画するエリア
    x, y = click_infos[2]
    cx, cy, wid, hei = __find_nearest_black_pixel(img, x, y, "cxcywh", margin)
    next_area = [cx, cy, wid, hei]

    click_infos = click_infos[3:]  # 使ったものはremove
    button_area = []
    for i in range(0, len(click_infos), 2):
        for j in range(2):
            x, y = click_infos[i + j]
            cx, cy, wid, hei = __find_nearest_black_pixel(img, x, y, "cxcywh", margin)
            if j == 0:  # 左端ボタンの場合は記録して右端ボタンに移る
                box_cx1 = cx
                continue
            # box1cxからbox2cxまで黒線が何本あるかカウントして、ボタンの数を導出する
            num = __calculate_button_num(img, box_cx1, cx, cy, margin)
            button_area.append([box_cx1, cx, cy, wid, hei, num])

    with open(conf_filename, "w", newline='') as f:
        writer = csv.writer(f)
        writer.writerow([width, height])
        writer.writerow(title_area)
        writer.writerow(prev_area)
        writer.writerow(next_area)
        writer.writerows(button_area)


def Play(subject_num, trial_num, start_num = 1, size=1.0, zero_mean = True):
    global _x
    global _y
    global _touch_flag

    print('参加者：{}人目、試行回数：{}回、{}試行目からスタート'.format(subject_num, trial_num, start_num))

    window_name = 'Questionnaire Form'
    img = cv2.imread(sheet_filename)

    t = start_num

    while t <= trial_num:

        form = Form(img, window_name, t, size)
        form.SetMouseEvent(__mouse_event)

        while not form.IsGotoNextState() and not form.IsGotoPrevState():
            if _touch_flag:
                form.Update(_x, _y)
                _touch_flag = False
            form.RenderAll(_x, _y)

        cv2.destroyAllWindows()

        # 前に戻るボタンがONならこの試行の結果を無視して前に戻る
        if form.IsGotoPrevState():
            t = (t - 1) if t != 0 else t
            cv2.waitKey(500)
            continue

        _data, _qnum = form.GetData(zero_mean)
        dt = datetime.datetime.now()

        record = [t] + [_data[f'q{i+1}'] for i in range(_qnum)] + [dt]

        save_filename = result_prename + str(subject_num) + result_etcname
        if not os.path.isfile(save_filename):
            with open(save_filename, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['trial'] + [f'q{i+1}' for i in range(_qnum)] + ['time_stamp'])
        with open(save_filename, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(record)

        cv2.waitKey(500)
        t += 1        


if __name__ == '__main__':
    argv = sys.argv[1:]
    subject_num = None
    trial_num = None
    start_num = 1
    size_gain = 1.0
    zero_mean = True

    try:
        opts, args = getopt.getopt(argv, 'h:u:t:s:g:z:d', ['help', 'user=', 'trial=', 'start=', 'gain=', 'zmean=', 'debug'])
    except getopt.GetoptError:
        print(usage)
        sys.exit()
    for opt, arg in opts:
        try:
            if opt in ('-h', '--help'):
                print(usage)
                sys.exit()
            if opt in ('-d', '--debug'):
                FindFormParameter()
                sys.exit()
            elif opt in ('-u', '--user'):
                subject_num = int(arg)
            elif opt in ('-t', '--trial'):
                trial_num = int(arg)
            elif opt in ('-g', '--gain'):
                size_gain = float(arg)
            elif opt in ('-s', '--start'):
                start_num = int(arg)
                if start_num <= 0:
                    print(usage)
                    sys.exit()
            elif opt in ('-z', '--zmean'):
                zero_mean = True if int(arg) != 0 else False
        except Exception:
            print('Error parsing argument: %s' % opt)
            print(usage)
            sys.exit(2)
    if subject_num == None or subject_num <= 0:
        print(usage)
        sys.exit()
    Play(subject_num, trial_num, start_num, size_gain, zero_mean)