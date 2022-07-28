# Simple Questionnaire Form
## Requirement
- Python 3.x
- opencv-python

## How To Setup
1. powerpoint等を使って所望のアンケートシートの外観を作成し、sheet.pngとして保存する。  
　　※ Nextボタン、Prevボタン、第N試行を表示するところにも黒枠を作成する必要あり（sheet.png参考）。
2. ```python form.py --debug```を実行。  
2.a 第N試行のNを書く場所をクリック
2.b Prevボタンの領域をクリック  
2.c Nextボタンの領域をクリック  
2.d Question1のリッカート尺度の一番左端をクリック  
2.e Question1のリッカート尺度の一番右端をクリック  
2.f Questionの数だけd, eを繰り返す  
2.g 左上の水色四角の中をクリックするとresources/form_conf.csvが作成される  
3. ```python form.py -u [被験者番号] -t [全試行数]```を実行すると実行される  

