#!/usr/bin/env python
"""
実験概要:
  - ターゲット（奇数刺激）の有無を判断する視覚探索課題
  - 刺激: 円 vs 円＋棒
  - 反応キー: F（ターゲットあり）、J（ターゲットなし）
  - セットサイズ: 4, 8, 16
"""

import csv
import os
import sys
from psychopy import visual, core, event, monitors, gui
import numpy as np

# =============================================================================
# 実験パラメタ
# =============================================================================
dlg_dict = {'学籍番号': ''}
dlg = gui.DlgFromDict(dictionary=dlg_dict, title='学籍番号を入力してください', order=['学籍番号'])
if not dlg.OK:
    core.quit()
SUBJECT = (dlg_dict.get('学籍番号|0') or dlg_dict.get('学籍番号') or '').strip()
if SUBJECT == '':
    core.quit()
SET_SIZES = [4, 8, 16]   # 刺激セットサイズ
N_SET_SIZES = len(SET_SIZES)
P_TRIALS = 12            # 練習試行数
R_TRIALS = 20            # 繰り返し数
X_TRIALS = R_TRIALS * 2 * 2 * N_SET_SIZES  # 本実験試行数

MAX_WAIT = 5.0           # 反応時間の制限時間（秒）
FIXATION_DURATION = 0.5  # 注視点の表示時間（秒）

# 刺激描画パラメタ（ピクセル単位）
N_COLUMNS = 5
N_ROWS = 5
STROKE = 4               # 線の太さ（px）
MARGIN = 4               # 円のマージン（px）

# =============================================================================
# モニター設定（解像度は自動取得）
# =============================================================================
mon = monitors.Monitor('testMonitor')

# =============================================================================
# ウィンドウ作成（フルスクリーン）
# =============================================================================
win = visual.Window(
    fullscr=True,
    monitor=mon,
    units='pix',
    color=[0, 0, 0],
    colorSpace='rgb',
    allowGUI=False,
    waitBlanking=True,
)
win.mouseVisible = False

# 実際の解像度を取得
SCREEN_W, SCREEN_H = win.size

# グレー（PsychoPy rgb スケール）
GRAY  = [0, 0, 0]
BLACK = [-1, -1, -1]
WHITE = [1, 1, 1]

# =============================================================================
# 刺激レイアウト計算（画面高さの8割の正方形に収まるよう動的計算）
# =============================================================================
FIELD_SIZE = int(SCREEN_H * 0.7)           # 刺激提示領域のサイズ（正方形）
STIMULUS_RANGE = FIELD_SIZE // N_COLUMNS   # 1cellのサイズ
OBJECT_SIZE = int(STIMULUS_RANGE // 2 * 0.8)  # 刺激サイズ（cellの半分の80%）
JITTER = int(OBJECT_SIZE * 0.8)            # cellの中心からのバラツキ

col_centers = (np.arange(N_COLUMNS) + 0.5) * STIMULUS_RANGE
row_centers = (np.arange(N_ROWS) + 0.5) * STIMULUS_RANGE
XX, YY = np.meshgrid(col_centers, row_centers)

XX = XX - FIELD_SIZE / 2
YY = FIELD_SIZE / 2 - YY

N_POSITIONS = N_COLUMNS * N_ROWS
grid_positions = np.column_stack([XX.flatten(), YY.flatten()])

# =============================================================================
# 刺激オブジェクト生成関数
# =============================================================================

def make_circle_stim(win, pos=(0, 0)):
    """円のみ刺激"""
    r = (OBJECT_SIZE - MARGIN * 2) / 2
    return visual.Circle(
        win,
        radius=r,
        pos=pos,
        lineColor=BLACK,
        fillColor=None,
        lineWidth=STROKE,
        units='pix',
    )

def make_cplusline_stim(win, pos=(0, 0)):
    """円＋棒刺激
    """
    r = (OBJECT_SIZE - MARGIN * 2) / 2
    circle = visual.Circle(
        win,
        radius=r,
        pos=pos,
        lineColor=BLACK,
        fillColor=None,
        lineWidth=STROKE,
        units='pix',
    )
    # 棒の中点を円弧上（6時方向）に置く
    # 棒の長さ = r、中点 = (pos[0], pos[1] - r)
    half = r / 2
    line = visual.Line(
        win,
        start=(pos[0], pos[1] - r + half),   # 上端: 円弧より half だけ上
        end=  (pos[0], pos[1] - r - half),   # 下端: 円弧より half だけ下
        lineColor=BLACK,
        lineWidth=STROKE,
        units='pix',
    )
    return circle, line

def make_fixation(win):
    """十字の注視点"""
    h_line = visual.Line(win, start=(-OBJECT_SIZE/2, 0), end=(OBJECT_SIZE/2, 0),
                         lineColor=BLACK, lineWidth=STROKE, units='pix')
    v_line = visual.Line(win, start=(0, -OBJECT_SIZE/2), end=(0, OBJECT_SIZE/2),
                         lineColor=BLACK, lineWidth=STROKE, units='pix')
    return h_line, v_line

# =============================================================================
# キー待ちヘルパー（ESCで即終了）
# =============================================================================
def wait_key():
    """任意キー待ち。ESCが押された場合はデータファイルを閉じて終了。"""
    keys = event.waitKeys()
    if keys and 'escape' in keys:
        try:
            data_file.close()
        except Exception:
            pass
        win.close()
        core.quit()

# =============================================================================
# データファイルの設定
# =============================================================================
DATA_FILENAME = f'{SUBJECT}.csv'
write_header = not os.path.exists(DATA_FILENAME)

data_file = open(DATA_FILENAME, 'a', newline='', encoding='utf-8')
writer = csv.writer(data_file)
if write_header:
    writer.writerow(['subject', 'practice/real', 'trial#',
                     'target/nontarget', 'target_type', 'setsize',
                     'error', 'responsetime_ms'])

def write_trial(subject, block, trial, target, whichtarget, setsize, err, rt_ms):
    writer.writerow([subject, block, trial, target, whichtarget, setsize, err, rt_ms])
    data_file.flush()

# =============================================================================
# 注視点
# =============================================================================
fix_h, fix_v = make_fixation(win)

# =============================================================================
# 教示文の表示
# =============================================================================
instructions = [
    "Your task is to detect the presence of the odd target in the distractors.",
    "If the target exists,  press 'F' key with your left hand.",
    "If not,  press 'J' key with your right hand.",
    "Please respond as accurately and quickly as possible.",
    f"The number of practice trials is: {P_TRIALS}  and the number of experimental trials is: {X_TRIALS}",
    "",
    "Press any key to start",
]
instr_stims = []
line_height = 40
start_y = (len(instructions) - 1) * line_height / 2
for i, line in enumerate(instructions):
    stim = visual.TextStim(
        win,
        text=line,
        pos=(0, start_y - i * line_height),
        color=BLACK,
        height=24,
        units='pix',
        wrapWidth=SCREEN_W * 0.85,
    )
    instr_stims.append(stim)

win.flip()
for stim in instr_stims:
    stim.draw()
win.flip()
wait_key()
core.wait(1.0)

# =============================================================================
# 実験ループ
# =============================================================================
clock = core.Clock()

for block in range(1, 3):
    if block == 1:
        block_label = 'Practice'
        n_trials = P_TRIALS
    else:
        block_label = 'Test'
        n_trials = X_TRIALS

    # ブロック開始メッセージ
    msg = visual.TextStim(
        win,
        text=f'Press any Key to start   ({block_label} = {n_trials} trials)',
        pos=(0, 0),
        color=BLACK,
        height=24,
        units='pix',
    )
    msg.draw()
    win.flip()
    wait_key()
    core.wait(0.5)

    # 試行順序のシャッフル（本試行のみ使用）
    trial_sequence = np.random.permutation(n_trials) + 1  # 1-indexed

    for trial in range(1, n_trials + 1):
        win.flip()  # 画面クリア

        # ------------------------------------------------------------------
        # 刺激条件の設定
        # ------------------------------------------------------------------
        if block == 1:
            # 練習試行: ランダム
            target      = np.random.randint(1, 3)   # 1=あり, 2=なし
            whichtarget = np.random.randint(1, 3)   # 1=円がターゲット, 2=円+棒がターゲット
            set_size    = SET_SIZES[np.random.randint(0, N_SET_SIZES)]
        else:
            # 本試行: MATLABコードと同じロジックを再現
            ts = trial_sequence[trial - 1]
            target      = (ts - 1) % 2 + 1
            whichtarget = int(np.ceil(ts / (2 * N_SET_SIZES * R_TRIALS)))
            set_size    = SET_SIZES[int(np.ceil(((ts - 1) % (2 * N_SET_SIZES * R_TRIALS) + 1) / (2 * R_TRIALS))) - 1]

        # 位置のランダム配置
        position_index = np.random.permutation(N_POSITIONS)

        # ------------------------------------------------------------------
        # 刺激の生成
        # ------------------------------------------------------------------
        stim_objects = []   # (stim_type, pos) を格納: stim_type = 'circle' or 'cplusline'

        for i in range(set_size):
            pos_idx = position_index[i]
            base_x, base_y = grid_positions[pos_idx]

            # ジッター: MATLABの round(ceil(jitter*rand) - jitter/2) を再現
            dx = round(np.random.randint(1, JITTER + 1) - JITTER / 2)
            dy = round(np.random.randint(1, JITTER + 1) - JITTER / 2)
            pos = (base_x + dx, base_y + dy)

            # どの刺激を描くか決定
            if whichtarget == 1:   # 円がターゲット
                if target == 1 and i == 0:
                    item_type = 'circle'
                else:
                    item_type = 'cplusline'
            else:                  # 円+棒がターゲット
                if target == 1 and i == 0:
                    item_type = 'cplusline'
                else:
                    item_type = 'circle'

            stim_objects.append((item_type, pos))

        # ------------------------------------------------------------------
        # 注視点提示
        # ------------------------------------------------------------------
        fix_h.draw()
        fix_v.draw()
        win.flip()
        core.wait(FIXATION_DURATION)

        # ------------------------------------------------------------------
        # 刺激提示
        # ------------------------------------------------------------------
        for item_type, pos in stim_objects:
            if item_type == 'circle':
                s = make_circle_stim(win, pos=pos)
                s.draw()
            else:
                c, l = make_cplusline_stim(win, pos=pos)
                c.draw()
                l.draw()
        event.clearEvents()  # 注視点提示中のキー入力を破棄
        win.flip()

        # ------------------------------------------------------------------
        # 反応取得
        # ------------------------------------------------------------------
        clock.reset()
        response = None
        rt_ms = 0
        err = None

        while response is None and clock.getTime() < MAX_WAIT:
            keys_pressed = event.getKeys(
                keyList=['f', 'j', 'escape'],
                timeStamped=clock,
            )
            if keys_pressed:
                key, t = keys_pressed[0]
                response = key
                rt_ms = round(t * 1000)

        # ------------------------------------------------------------------
        # 正誤判定
        # ------------------------------------------------------------------
        if response is None:
            err = 3
            feedback_text = 'Time out!'
            rt_ms = 0
        elif response == 'escape':
            data_file.close()
            win.close()
            core.quit()
        elif response == 'f':
            response_key = 1   # f = ターゲットあり
            if response_key == target:
                err = 0
                feedback_text = 'Correct!'
            else:
                err = 1
                feedback_text = 'Wrong!'
        elif response == 'j':
            response_key = 2   # j = ターゲットなし
            if response_key == target:
                err = 0
                feedback_text = 'Correct!'
            else:
                err = 1
                feedback_text = 'Wrong!'

        # ------------------------------------------------------------------
        # データ書き込み
        # ------------------------------------------------------------------
        write_trial(SUBJECT, block, trial, target, whichtarget, set_size, err, rt_ms)

        # ------------------------------------------------------------------
        # フィードバック表示
        # ------------------------------------------------------------------
        fb_stim = visual.TextStim(
            win,
            text=f'{feedback_text} /   RT = {rt_ms} ms',
            pos=(0, 0),
            color=BLACK,
            height=24,
            units='pix',
        )
        fb_stim.draw()
        win.flip()
        core.wait(1.0)

# =============================================================================
# 終了処理
# =============================================================================
data_file.write('\n')
data_file.close()

end_stim1 = visual.TextStim(win, text='All done! Thank you for participating',
                             pos=(0, 40), color=BLACK, height=24, units='pix')
end_stim2 = visual.TextStim(win, text='Press any key',
                             pos=(0, 0), color=BLACK, height=24, units='pix')
end_stim1.draw()
end_stim2.draw()
win.flip()
wait_key()

win.close()
core.quit()