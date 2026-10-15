with open(r'C:\Users\w50057230\Downloads\FWA project\report_v4\chapters\step6_address_coverage.tex', 'r') as f:
    content = f.read()
import re
for m in re.finditer(r'430|305|2\.5%|3\.5%|23\.9%|17\.9%', content):
    start = max(0, m.start()-50)
    end = min(len(content), m.end()+50)
    print(f'Found "{m.group()}" at {m.start()}: ...{content[start:end]}...')
