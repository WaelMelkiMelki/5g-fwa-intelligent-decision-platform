import fitz
doc = fitz.open(r'C:\Users\w50057230\Downloads\FWA project\report_v4\main.pdf')
text = ''
for page in doc:
    text += page.get_text()

patterns = [
    '2,629',
    '9,783',
    '9,674',
    '109',
    '2,338',
    '291',
    '21.2%',
    '78.8%',
    '77.9%',
    '0.9%',
    '98.9%',
    '2,629 CPE',
    'Fiber_Cannibalization',
    'RF_Failure',
    'Cell_Overload',
    'handset readiness',
    'handset_5g_ready_flag',
]

for p in patterns:
    if p in text:
        print(f'FOUND: "{p}"')
    else:
        print(f'MISSING: "{p}"')

doc.close()
