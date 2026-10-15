import re
import os

patterns_to_check = [
    '2,923',
    '2923',
    '9,489',
    '9489',
    '9,449',
    '9449',
    '305',
    '40 fibre',
    '40 fiber',
    '40 &',
    '23.5%',
    '76.5%',
    '76.1%',
    '0.3%',
    '99.6%',
    '0.4%',
    'RF failures account for 99.6%',
    '2,923 CPE',
    'FIBER_COMPETITOR',
    'INFEAISBLE',
    'CAPACITY_CONSTRAINED',
    'device_5g_ready_flag',
    'No 5G Device',
    '5G-ready device',
    'device readiness',
    'Fiber_Competitor & 305',
    'Fiber_Competitor cases (0.3%)',
    '430',
    '2,228',
    '23.9%',
    '17.9%',
    '2.5%',
    '3.5% (430)',
    '23.9%',
    '17.9%',
    '2.5%',
    '3.5% (430)',
]

chapter_dir = r'C:\Users\w50057230\Downloads\FWA project\report_v4\chapters'
found_any = False

for fname in os.listdir(chapter_dir):
    if fname.endswith('.tex'):
        fpath = os.path.join(chapter_dir, fname)
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        for pattern in patterns_to_check:
            if pattern in content:
                print(f'FOUND in {fname}: "{pattern}"')
                found_any = True

if not found_any:
    print('SUCCESS: No stale patterns found in any chapter file!')
else:
    print('\nWARNING: Some stale patterns still found.')
