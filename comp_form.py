import numpy as np
import copy
import os
import csv
import datetime
import cv2

import getopt
import sys

# from socket import socket, AF_INET, SOCK_DGRAM
# def send_msg(msg):
#     s = socket(AF_INET, SOCK_DGRAM) # 通信する場合
#     s.sendto(msg.encode(), ("100.80.145.215", 52525))
#     s.close()


usage = '''comp_form.py usage:

python comp_form.py <options>
        --user=<number>  1~
        --trial=<number>  (default : 0)
'''

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

# 二次元マップ
class Map:
    def __init__(self, center_x, center_y, width, height, margin_gain=1.0):
        self.cx = center_x
        self.cy = center_y
        self.minx = (int)(center_x - width / 2 + 0.5)
        self.maxx = (int)(center_x + width / 2 + 0.5)
        self.miny = (int)(center_y - height / 2 + 0.5)
        self.maxy = (int)(center_y + height / 2 + 0.5)
        self.state = False
        # ボタン中心からどれだけ離れた範囲をクリック領域とみなすか
        self.margin_gain = margin_gain
        self.marginx = (int)(width / 2 * self.margin_gain + 0.5) 
        self.marginy = (int)(height / 2 * self.margin_gain + 0.5)
        self.posX = None
        self.posY = None
    
    # 戻り値：ステータス変更！
    def UpdateState(self, x, y):
        if not self.IsClick(x, y):
            return False 
        self.posX = self.maxx if x > self.maxx else self.minx if x < self.minx else x
        self.posY = self.maxy if y > self.maxy else self.miny if y < self.miny else y
        return True
    
    def IsClick(self, x, y):
        if x < self.cx - self.marginx or x > self.cx + self.marginx or y < self.cy - self.marginy or y > self.cy + self.marginy:
            return False
        else:
            return True

    def Render(self, target_img, color = (0, 0, 255), point_size = 5):
        if self.posX == None or self.posY == None:
            return 
        cv2.circle(target_img, (self.posX, self.posY), point_size, color, thickness=-1)

    def RenderMarginArea(self, target_img, color = (0, 255, 255)):
        cv2.rectangle(target_img, (self.cx - self.marginx, self.cy - self.marginy), 
                    (self.cx + self.marginx, self.cy + self.marginy), color, thickness=-1)

    # -1 ~ 1, -1 ~ 1で返す
    def State(self):
        if self.posX == None or self.posY == None:
            return (None, None)
        xvalue = -1 + 2 * (self.posX - self.minx) / (self.maxx - self.minx)
        yvalue = -1 * (-1 + 2 * (self.posY - self.miny) / (self.maxy - self.miny))
        return (xvalue, yvalue)





# フォーム
class Form:
    def __init__(self, back_img, window_name, trial_num, size=1.5):
        f = lambda a:(int)(a * size + 0.5)

        if not os.path.isfile("./resources/form_conf.csv"):
            print("resources/form_conf.csvがありません")
            sys.exit()
        with open("./resources/form_conf.csv", "r") as z:
            reader = csv.reader(z)
            dummy = [row for row in reader]
            imgw = (int)(dummy[0][0])
            imgh = (int)(dummy[0][1])
            t = {"x":(int)(dummy[1][0]), "y":(int)(dummy[1][1]), "w":(int)(dummy[1][2]), "h":(int)(dummy[1][3])}
            p = {"x":(int)(dummy[2][0]), "y":(int)(dummy[2][1]), "w":(int)(dummy[2][2]), "h":(int)(dummy[2][3])}
            n = {"x":(int)(dummy[3][0]), "y":(int)(dummy[3][1]), "w":(int)(dummy[3][2]), "h":(int)(dummy[3][3])}
            g = [{"x1":(int)(row[0]), "x2":(int)(row[1]), "y":(int)(row[2]), "w":(int)(row[3]), "h":(int)(row[4])} for row in dummy[4:]]

        self.form_width = f(imgw)
        self.form_height = f(imgh)

        self.img = copy.deepcopy(back_img)
        self.img = cv2.resize(self.img, (self.form_width, self.form_height))
        self.window_name = window_name
        cv2.namedWindow(self.window_name)
        cv2.moveWindow(self.window_name, 0, 0)
        self.trial_num = trial_num
        cv2.rectangle(self.img, (f(t['x']) - 2, f(t['y'] - t['h'] / 2) - 2), (f(t['x'] + t['w']) + 2, f(t['y'] + t['h'] / 2) + 2), (255, 255, 255), -1)
        cv2.putText(self.img, "Trial : " + str(trial_num + 1), (f(t['x']), f(t['y'])), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 0), 3)

        self.all_questions = []
        idx = 0

        # Question1
        buttons_num = 7
        buttons_width = f(g[idx]["w"])  
        buttons_height = f(g[idx]["h"])    
        q2_yc = f(g[idx]["y"])          
        q2_xmin = f(g[idx]["x1"])
        q2_xmax = f(g[idx]["x2"]) 
        q2_xcs = [int(q2_xmin + i * (q2_xmax - q2_xmin) / (buttons_num - 1) + 0.5) for i in range(buttons_num)]
        buttons = []
        for i in range(buttons_num):
            buttons.append(Button(q2_xcs[i], q2_yc, buttons_width, buttons_height, margin_gain=2.4))
        self.question1 = RadioButton(buttons)
        idx += 1
        self.all_questions.append(self.question1)

        # Question2
        buttons_num = 7
        buttons_width = f(g[idx]["w"]) 
        buttons_height = f(g[idx]["h"]) 
        q2_yc = f(g[idx]["y"]) 
        q2_xmin = f(g[idx]["x1"]) 
        q2_xmax = f(g[idx]["x2"]) 
        q2_xcs = [int(q2_xmin + i * (q2_xmax - q2_xmin) / (buttons_num - 1) + 0.5) for i in range(buttons_num)]
        buttons = []
        for i in range(buttons_num):
            buttons.append(Button(q2_xcs[i], q2_yc, buttons_width, buttons_height, margin_gain=2.4))
        self.question2 = RadioButton(buttons)
        idx += 1
        self.all_questions.append(self.question2)

        # # # Question3
        # buttons_num = 7
        # buttons_width = f(g[idx]["w"]) 
        # buttons_height = f(g[idx]["h"]) 
        # q2_yc = f(g[idx]["y"])
        # q2_xmin = f(g[idx]["x1"]) 
        # q2_xmax = f(g[idx]["x2"]) 
        # q2_xcs = [int(q2_xmin + i * (q2_xmax - q2_xmin) / (buttons_num - 1) + 0.5) for i in range(buttons_num)]
        # buttons = []
        # for i in range(buttons_num):
        #     buttons.append(Button(q2_xcs[i], q2_yc, buttons_width, buttons_height, margin_gain=2.4))
        # self.question3 = RadioButton(buttons)
        # idx += 1
        # self.all_questions.append(self.question3)

        # Prev
        self.prev_button = Button(f(p['x']), f(p['y']), f(p['w']), f(p['h']), "prev")
        # Next
        self.next_button = Button(f(n['x']), f(n['y']), f(n['w']), f(n['h']), "next")

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
    
    def GetData(self):
        row = {}
        for i, question in enumerate(self.all_questions):
            row[f'q{i+1}'] = question.State()
        return row

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


def LoadConditionFile(file_name):
    i2j = []
    with open(file_name, 'r', newline='') as f:
        reader = csv.reader(f)
        dummy = [row for row in reader]

        for d in dummy[1:]:
            row = {'trial':(int)(d[0]), 'Factor1':d[1], 'Factor2':d[2]}
            i2j.append(row)
    print(i2j)
    return i2j


def FindFormParameter():
    global _x
    global _y
    global _touch_flag
    sheet_name = './resources/sheet.png'
    img = cv2.imread(sheet_name)
    cv2.namedWindow("debug")
    cv2.moveWindow("debug", 0, 0)
#    cv2.imshow("debug", img)
    cv2.setMouseCallback("debug", __mouse_event)

    print("1. title area\n2. prev_button\n3. next_button\n4. question1...")

    width = img.shape[1]
    height = img.shape[0]
    thx = 20
    thy = 20
    cv2.rectangle(img, (0, 0), (thx, thy), (255, 255, 0))
    cands = [[-1, -1]]

    while True:
        bar_img = img.copy()
        cv2.circle(bar_img, (_x, _y), 5, (0, 255, 0), -1)
        cv2.imshow("debug", bar_img)
        if _touch_flag:
            if _x < thx and _y < thy:
                break
            cands.append([_x, _y])
            cv2.circle(img, (_x, _y), 5, (0, 0, 255), -1)
            _touch_flag = False
        cv2.waitKey(5)
    cv2.destroyWindow("debug")

    row = []
    title_area = []
    p_n_button = []
    img = cv2.imread(sheet_name)
    for i in range(0, len(cands), 2):
        for j in range(2):
            p = cands[i + j]
            top = p[1]
            bot = p[1]
            left = p[0]
            right = p[0]
            while img[top, p[0], 0] > 250:
                top -= 1
            while img[bot, p[0], 0] > 250:
                bot += 1
            while img[p[1], left, 0] > 250:
                left -= 1
            while img[p[1], right, 0] > 250:
                right += 1
            box_width = right - left
            box_height = bot - top
            if i == 0:
                if j == 1:
                    title_area.append([(int)(left), (int)(top + box_height / 2 + 0.5), box_width + 4, box_height + 4, -1])
                continue
            if i == 2:
                p_n_button.append([(int)(left + box_width / 2 + 0.5), (int)(top + box_height / 2 + 0.5), box_width + 4, box_height + 4, -1])
                continue
            if j == 0:
                box_cx1 = (int)(left + box_width / 2 + 0.5)
            else:
                box_cx2 = (int)(left + box_width / 2 + 0.5)
                box_cy2 = (int)(top + box_height / 2 + 0.5)
                row.append([box_cx1, box_cx2, box_cy2, box_width + 4, box_height + 4])
    

    with open("./resources/form_conf.csv", "w", newline='') as f:
        writer = csv.writer(f)
        writer.writerow([width, height, 0, 0, 0])
        writer.writerow(title_area[0])
        writer.writerow(p_n_button[0])
        writer.writerow(p_n_button[1])
        writer.writerows(row)





def Play(subject_num, start_num = 0):
    global _x
    global _y
    global _touch_flag

    header = ["trial", "Factor1", "Factor2", "q1", "q2", "time"]

    conds = copy.deepcopy(LoadConditionFile('conditions/subject{}.csv'.format(subject_num)))
    trial_num = len(conds)  #.shape[0]    
    print('参加者：{}人目、試行回数：{}回、{}試行目からスタート'.format(subject_num, trial_num, start_num + 1))
    t = start_num

    img = cv2.imread('./resources/sheet.png')
    window_name = 'target'
    res = []


    while t < trial_num:
        form = Form(img, window_name, t, size=0.9)
        form.SetMouseEvent(__mouse_event)

        while not form.IsGotoNextState() and not form.IsGotoPrevState():
            if _touch_flag:
                form.Update(_x, _y)
                _touch_flag = False
            ans = form.RenderAll(_x, _y)

            # if ans == 49:
            #     send_msg(f"a,o,1,end")
            # elif ans == 50:
            #     send_msg(f"a,o,2,end")

        cv2.destroyAllWindows()

        # 前に戻るボタンがONならこの試行の結果を無視して前に戻る
        if form.IsGotoPrevState():
            if t != 0:
                t += -1
            # send_msg(f"a,n,{t + 1},end")
            cv2.waitKey(500)
            continue

        _data = form.GetData()

        dt = datetime.datetime.now()
        record = [t, conds[t]['Factor1'], conds[t]['Factor2'], \
            _data['q1'] - 3, _data['q2'] - 3, dt]
        res.append(record)

        if not os.path.isfile('result/result_tmp{}.csv'.format(subject_num)):
            with open('result/result_tmp{}.csv'.format(subject_num), 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(header)
        with open('result/result_tmp{}.csv'.format(subject_num), 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(record)

        # 結果を送信する
        # send_msg(f"a,n,{t+2},end")

        ###########################
        cv2.waitKey(500)
        t += 1        

    # with open('result/result{}.csv'.format(subject_num), 'w', newline='') as f:
    #     writer = csv.writer(f)
    #     writer.writerow(header)
    #     writer.writerows(res)



if __name__ == '__main__':
    argv = sys.argv[1:]
    subject_num = None
    trial_num = 0

    try:
        opts, args = getopt.getopt(argv, 'h:u:t:d:', ['help', 'user=', 'trial=', 'debug'])
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
                if trial_num < 0:
                    print(usage)
                    sys.exit()
        except Exception:
            print('Error parsing argument: %s' % opt)
            print(usage)
            sys.exit(2)
    if subject_num == None or subject_num <= 0:
        print(usage)
        sys.exit()
    Play(subject_num, trial_num)