import re
import os

# Only check for truly stale patterns (exact matches that should have been replaced)
stale_patterns = [
    r'2,923',      # old eligible count
    r'9,489',      # old excluded count
    r'9,449',      # old RF failures
    r'9449',       # old RF failures (no comma)
    r'305',        # old Fiber_Competitor count
    r'40 fibre',   # old fibre exclusions
    r'40 fiber',   # old fiber exclusions
    r'23\.5\%',    # old eligible %
    r'76\.5\%',    # old excluded %
    r'76\.1\%',    # old RF %
    r'0\.3\%',     # old fibre %
    r'99\.6\%',    # old RF % of exclusions
    r'0\.4\%',     # old fibre % of exclusions
    r'RF failures account for 99\.6\%',
    r'2,923 CPE',  # old CPE count
    r'FIBER_COMPETITOR',  # old exclusion reason name
    r'INFEAISBLE',  # old exclusion reason name
    r'CAPACITY_CONSTRAINED',  # old exclusion reason name
    r'device_5g_ready_flag',  # old column name
    r'No 5G Device',  # old penalty name
    r'5G-ready device',  # old term
    r'device readiness',  # old term
    r'Fiber_Competitor & 305',  # old count
    r'Fiber_Competitor cases \(0\.3\%\)',
    r'430',        # old 5G_Feasible
    r'2,228',      # old 4G_Fallback
    r'23\.9\%',    # old Infeasible %
    r'17\.9\%',    # old 4G_Fallback %
    r'2\.5\%',     # old Fiber_Competitor %
    r'3\.5% \(430\)',  # old 5G_Feasible %
    r'2\.5% \(305\)',  # old Fiber_Competitor %
]

chapter_dir = r'C:\Users\w50057230\Downloads\FWA project\report_v4\chapters'
found_any = False

for fname in os.listdir(chapter_dir):
    if fname.endswith('.tex'):
        fpath = os.path.join(chapter_dir, fname)
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        for pattern in stale_patterns:
            matches = list(re.finditer(pattern, content))
            if matches:
                for m in matches:
                    start = max(0, m.start()-50)
                    end = min(len(content), m.end()+50)
                    print(f'FOUND in {fname}: pattern "{pattern}" at {m.start()}: ...{content[start:end]}...')
                    found_any = True

if not found_any:
    print('SUCCESS: No stale patterns found in any chapter file!')
else:
    print(f'\nTotal stale pattern occurrences: {found_any}')
