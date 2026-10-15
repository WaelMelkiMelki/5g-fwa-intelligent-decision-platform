import re
import os

# Define replacements
replacements = [
    # Eligible count
    (r'2,923', '2,629'),
    (r'2923', '2629'),
    # Excluded count
    (r'9,489', '9,783'),
    (r'9489', '9783'),
    # RF Failure exclusions
    (r'9,449', '9,674'),
    (r'9449', '9674'),
    # Fiber exclusions
    (r'40 fibre', '109 fibre'),
    (r'40 fiber', '109 fiber'),
    (r' 40 &', ' 109 &'),
    # Fiber_Competitor
    (r'305', '109'),
    # Percentages
    (r'23\.5\%', '21.2\%'),
    (r'23.5%', '21.2%'),
    (r'76\.5\%', '78.8\%'),
    (r'76.5%', '78.8%'),
    (r'76\.1\%', '77.9\%'),
    (r'76.1%', '77.9%'),
    (r'0\.3\%', '0.9\%'),
    (r'0.3%', '0.9%'),
    (r'99\.6\%', '98.9\%'),
    (r'99.6%', '98.9%'),
    (r'0\.4\%', '1.1\%'),
    (r'0.4%', '1.1%'),
    # RF failures text
    (r'RF failures account for 99.6%', 'RF failures account for 98.9%'),
    (r'RF failures account for 99\.6%', 'RF failures account for 98.9%'),
    # 2,923 CPE units
    (r'~2,923 CPE', '~2,629 CPE'),
    (r'2,923 CPE', '2,629 CPE'),
    # device penalty references
    (r'device_5g_ready_flag', 'handset_5g_ready_flag'),
    (r'No 5G Device', ''),
    (r'No 5G-ready device', ''),
    (r'device readiness', 'handset readiness'),
    (r'5G-ready device', '5G-handset'),
    (r'5G-ready devices', '5G-handsets'),
    # Fiber_Competitor count
    (r'Fiber_Competitor & 305', 'Fiber_Competitor & 109'),
    (r'Fiber_Competitor cases \(0.3\%\)', 'Fiber_Competitor cases (0.9%)'),
    # Exclusion reason names
    (r'FIBER_COMPETITOR', 'Fiber_Cannibalization'),
    (r'INFEAISBLE', 'RF_Failure'),
    (r'CAPACITY_CONSTRAINED', 'Cell_Overload'),
    # 5G_Feasible count
    (r'430', '291'),
    (r'4G_Fallback.*2,228', '4G_Fallback & 2,338'),
    (r'2,228.*4G_Fallback', '2,338 4G_Fallback'),
    # Eligible percentage
    (r'23\.9\%', '21.2%'),
    (r'23.9%', '21.2%'),
    (r'17\.9\%', '18.8%'),
    (r'17.9%', '18.8%'),
    (r'2\.5\%', '0.9%'),
    (r'2.5%', '0.9%'),
    # 5G_Feasible count
    (r'3.5\% \(430\)', '2.3% (291)'),
    (r'3.5% (430)', '2.3% (291)'),
]

def apply_replacements(content):
    for pattern, repl in replacements:
        content = re.sub(pattern, repl, content)
    return content

# Process chapter files
chapter_dir = r'C:\Users\w50057230\Downloads\FWA project\report_v4\chapters'
files = [
    'step13_recommendation_engine.tex',
    'step14_capacity_simulation.tex',
    'step15_final_prioritisation.tex',
    'step12_churn_model.tex',
    'step6_address_coverage.tex',
    'integrated_results_analysis.tex',
    'step12_churn_model.tex',
    'chapter1.tex',
    'chapter8_abt.tex',
    'abstract.tex',
    'appendix/appendix.tex',
]

for fname in files:
    fpath = os.path.join(chapter_dir, fname)
    if os.path.exists(fpath):
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        new_content = apply_replacements(content)
        if new_content != content:
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"Updated: {fname}")
        else:
            print(f"No changes: {fname}")
    else:
        print(f"Not found: {fname}")

print("Batch replacements complete.")
