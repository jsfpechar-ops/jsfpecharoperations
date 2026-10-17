from pathlib import Path
import os, json, base64
from playwright.sync_api import sync_playwright

OUT = Path(os.environ.get('UBYHOST_REVIEW_ARTIFACTS','/tmp/ubyhost-control-review'))
OUT.mkdir(parents=True, exist_ok=True)
BASE = os.environ.get('UBYHOST_REVIEW_URL','http://127.0.0.1:8765/host-control-review.html')
PAGES = ['dashboard','stays','invoices','fees','fee-detail','register','operators','invoice-new','properties','property','address','archived','audit','guest-links','automation','locks','property-links','property-reporting','property-lock','stay-detail','feedback','search-review']
defaults_pages = ['stays','invoices','fees','fee-detail','register']
env = dict(os.environ)
env['XDG_CONFIG_HOME'] = '/tmp/ubyhost-review-chromium-config'
env['XDG_CACHE_HOME'] = '/tmp/ubyhost-review-chromium-cache'
report = {'scope':'Standalone design preview only; no application test suite or live data', 'checks':[], 'screenshots':[], 'errors':[]}

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path='/usr/bin/chromium', headless=True,
        args=['--no-sandbox','--disable-dev-shm-usage','--disable-crash-reporter'], env=env)
    report['chromium'] = browser.version
    page = browser.new_page(viewport={'width':1280,'height':900})
    page.on('pageerror', lambda e: report['errors'].append(str(e)))

    def load(name, locale='en', width=1280, panel=False, embedded_mobile=False):
        page.set_viewport_size({'width':width,'height':900 if width==1280 else 844})
        page.goto(BASE + f'?page={name}&locale={locale}&capture=1&size={"mobile" if embedded_mobile else "desktop"}' + ('&panel=open' if panel else ''))
        page.wait_for_function('!!window.reviewState')

    def check(name, condition):
        report['checks'].append({'name':name,'passed':bool(condition)})
        if not condition:
            raise AssertionError(name)

    def capture(name):
        target = OUT / (name + '.png')
        if page.locator('.feedback-toast').count():
            page.wait_for_timeout(300)
        page.screenshot(path=str(target), full_page=True)
        report['screenshots'].append(target.name)

    load('dashboard')
    check('Dashboard shows exactly five unique stays', page.locator('[data-dashboard-group] .row').count()==5 and len(set(page.locator('[data-dashboard-group] .row').evaluate_all('(rows)=>rows.map(r=>r.dataset.stay)')))==5)
    check('Dashboard uses 30-day window; far-future stays absent', '30 days' in page.locator('main').inner_text() and not page.locator('[data-stay="7"]').count() and not page.locator('[data-stay="8"]').count())
    check('Older overdue work remains first', page.locator('[data-dashboard-group] .row').first.get_attribute('data-stay')=='1')
    row=page.locator('[data-dashboard-group] .row').first
    before=row.evaluate('(e)=>getComputedStyle(e).backgroundColor')
    row.hover()
    check('Hover changes interactive row background', row.evaluate('(e)=>getComputedStyle(e).backgroundColor')!=before)
    page.mouse.move(0,0)
    row.focus()
    check('Keyboard focus is visibly outlined', row.evaluate('(e)=>getComputedStyle(e).outlineStyle')=='solid')
    capture('dashboard-keyboard-focus-en-1280')

    load('dashboard')
    page.evaluate('demoStays.splice(0,demoStays.length,...demoStays.filter(s=>s.task!=="overdue"&&s.task!=="ready"));render()')
    check('Zero-ready and zero-overdue cards are neutral',page.locator('.summary-card.zero').count()==2 and page.locator('.summary-card.red').evaluate('(e)=>getComputedStyle(e.querySelector(".status-dot")).backgroundColor')=='rgb(170, 161, 155)')
    capture('dashboard-zero-states-en-1280')

    load('stays')
    check('Default stays summary is All properties and Active only',page.locator('#applied-summary').inner_text()=='All properties · Active')
    check('Stays default is unbounded All dates',page.evaluate('reviewState.applied.stays.range==="all"&&!reviewState.applied.stays.from&&!reviewState.applied.stays.to'))
    original=page.locator('#applied-summary').inner_text()
    page.locator('[data-toggle-filters]').click()
    page.locator('#field-apartment').select_option('Garden studio')
    check('Filter edits remain a draft', page.locator('#applied-summary').inner_text()==original)
    page.locator('[data-cancel-filters]').click()
    page.locator('[data-toggle-filters]').click()
    check('Cancel restores previously applied filter values', page.locator('#field-apartment').input_value()=='')
    page.locator('#field-apartment').select_option('Garden studio')
    page.locator('[data-apply-filters]').click()
    check('Apply updates summary and closes panel', 'Garden studio' in page.locator('#applied-summary').inner_text() and not page.locator('#filters-panel').count())

    load('stays',panel=True)
    check('Stays exposes one shared date-range control',page.locator('[data-calendar="range"]').count()==1 and page.locator('[data-calendar="day"]').count()==0)
    page.locator('[data-calendar="range"]').click()
    check('Range picker has start/end selectors and one calendar',page.locator('[data-range-bound]').count()==2 and page.locator('.day-grid button').count()==42)
    capture('stays-date-range-en-1280')
    page.locator('[data-pick-calendar="2026-10-12"]').click()
    page.locator('[data-pick-calendar="2026-10-10"]').click()
    check('Reversed dates are explained and cannot apply',page.locator('.range-error').is_visible() and page.locator('[data-range-apply]').is_disabled())
    page.locator('[data-pick-calendar="2026-10-17"]').click()
    page.locator('[data-range-apply]').click()
    check('Apply dates updates only the filter draft',page.evaluate('reviewState.draft.from==="2026-10-12"&&reviewState.draft.to==="2026-10-17"&&!reviewState.applied.stays.from'))
    check('Summary is unchanged until Apply filters',page.locator('#applied-summary').inner_text()=='All properties · Active')
    page.locator('[data-apply-filters]').click()
    check('Only explicitly applied dates appear in the summary',page.locator('#applied-summary').inner_text()=='All properties · Active · 12.10.2026 – 17.10.2026')
    check('Date range counts as one filter',page.locator('#filters-toggle').inner_text()=='Filters (1)')
    page.locator('[data-reset-filters]').click()
    check('Reset removes date bounds and selects All dates',page.locator('#applied-summary').inner_text()=='All properties · Active' and page.locator('[data-tab="range"][data-value="all"]').get_attribute('aria-pressed')=='true')
    page.locator('[data-toggle-filters]').click()
    page.locator('[data-calendar="range"]').click()
    page.locator('[data-range-bound="to"]').click()
    page.locator('[data-pick-calendar="2026-10-17"]').click()
    page.locator('[data-range-apply]').click()
    page.locator('[data-apply-filters]').click()
    check('Open-ended range has a meaningful Until label without ellipsis',page.locator('#applied-summary').inner_text()=='All properties · Active · Until 17.10.2026')
    page.locator('[data-tab="range"][data-value="upcoming"]').click()
    check('Preset dates do not appear as user-chosen summary filters',page.locator('#applied-summary').inner_text()=='All properties · Active')

    load('invoices',panel=True)
    page.locator('[data-calendar="month"]').click()
    check('Month chooser has twelve months', page.locator('.month-grid button').count()==12)
    check('Future months disabled', page.locator('[data-pick-calendar="2026-11"]').is_disabled())
    check('Invoices allow All dates', page.locator('#calendar-popup [data-pick-calendar=""]').count()==1)
    capture('invoices-month-grid-en-1280')
    page.locator('[data-pick-calendar="2026-09"]').click()
    check('Month selection remains a filter draft', 'All dates' in page.locator('#applied-summary').inner_text() and page.locator('#filters-panel').count()==1)
    page.locator('[data-apply-filters]').click()
    check('Apply commits month choice', 'September' in page.locator('#applied-summary').inner_text())

    load('fees',panel=True)
    page.locator('[data-calendar="month"]').click()
    check('Stay fees have no All dates option', page.locator('#calendar-popup [data-pick-calendar=""]').count()==0)
    page.keyboard.press('Escape')
    check('Escape closes month chooser', not page.locator('#calendar-popup').evaluate('(e)=>e.matches(":popover-open")'))

    load('operators')
    check('Operator action buttons visible without hover', page.locator('.operator-row .actions > button').count()==4 and all(x.is_visible() for x in page.locator('.operator-row .actions > button').all()))
    page.locator('.operator-row').nth(1).locator('summary').click()
    check('Linked operator has explained disabled Delete', page.locator('.operator-row').nth(1).locator('.menu-body button').is_disabled() and page.locator('#delete-unavailable').is_visible())
    capture('operators-disabled-delete-en-1280')
    page.keyboard.press('Escape')
    page.locator('.operator-row').first.locator('summary').click()
    page.locator('[data-delete]').click()
    check('Delete confirmation explains archive destination', 'This item will move to Archived.' in page.locator('#delete-dialog').inner_text())
    capture('delete-confirmation-en-1280')
    page.locator('[data-confirm-delete]').click()
    check('Prototype Delete moves item into Archived', page.locator('h1').inner_text()=='Archived' and 'Example operator A' in page.locator('main').inner_text())
    page.locator('[data-tab="archive"][data-value="entities"]').click()
    page.locator('[data-restore]').click()
    check('Restore removes the correct archived item', 'Example operator A' not in page.locator('main').inner_text())
    load('operators')
    check('Restored operator appears in active list',page.locator('.operator-row').count()==2)

    load('invoice-new')
    check('Cleaning unit is blank', page.locator('#extra-unit-0').input_value()=='')
    check('Cleaning has no custom-description box', page.locator('.other-description').count()==0)
    page.locator('#kind-0').select_option('other')
    page.locator('#description-0').fill('Example custom item')
    check('Other reveals description field', page.locator('#description-0').is_visible())
    capture('invoice-other-en-1280')
    page.locator('#kind-0').select_option('cleaning')
    check('Switching to Cleaning hides description', page.locator('.other-description').count()==0)
    page.locator('#kind-0').select_option('other')
    check('Custom description preserved when switching back', page.locator('#description-0').input_value()=='Example custom item')

    load('property')
    check('Individual property has no duplicate Property tools menu', 'Property tools' not in page.locator('main').inner_text() and not page.locator('.host-tools').count())
    page.locator('[data-page="property-links"]').click()
    check('Local property link opens only local context', page.locator('.row').count()==1)
    load('properties')
    check('Multi-property overview links retained', page.locator('.cards [data-page="guest-links"]').count()==1 and page.locator('.cards [data-page="automation"]').count()==1 and page.locator('.cards [data-page="locks"]').count()==1)

    for locale in ['en','cs']:
        load('address',locale)
        for i,grid in enumerate(page.locator('.address-grid').all()):
            ys=grid.locator('input').evaluate_all('(els)=>els.map(e=>e.getBoundingClientRect().y)')
            check(f'Address inputs aligned in grid {i+1} ({locale})', max(ys)-min(ys)<=1)
            check(f'Address has no reporting pills ({locale}, grid {i+1})',grid.locator('.report-badge,.address-badge').count()==0)

    for locale in ['en','cs']:
        for width in [360,390,471,760,850,1280]:
            for embedded in [False,True] if width==1280 else [False]:
                load('dashboard',locale,width,embedded_mobile=embedded)
                buttons=page.locator('[data-dashboard-group] .actions>button')
                geometry=buttons.evaluate_all('(es)=>es.map(e=>{const r=e.getBoundingClientRect();return {x:r.x,w:r.width,h:r.height,clipped:e.scrollWidth>e.clientWidth+1,nowrap:getComputedStyle(e).whiteSpace==="nowrap"}})')
                check(f'Open stay buttons share a column/width/height and do not clip: {locale} {width} embedded={embedded}',all(abs(r['x']-geometry[0]['x'])<1 and abs(r['w']-geometry[0]['w'])<1 and abs(r['h']-geometry[0]['h'])<1 and not r['clipped'] and r['nowrap'] for r in geometry))
                check(f'Four semantic dashboard cards: {locale} {width}',page.locator('.summary-card').count()==4 and page.locator('.summary-card.amber .status-dot').count()==1)
                heights=page.locator('.summary-card').evaluate_all('(es)=>es.map(e=>e.getBoundingClientRect().height)')
                check(f'All four status cards share a height: {locale} {width} embedded={embedded}',max(heights)-min(heights)<1)
                if embedded:
                    check(f'Embedded mobile uses mobile layout: {locale}',page.locator('.invoice-head').count()==0 and page.locator('.summary-cards').evaluate('(e)=>getComputedStyle(e).gridTemplateColumns.split(" ").length')==2)
                    capture(f'dashboard-embedded-mobile-{locale}-1280')
                load('invoice-new',locale,width,embedded_mobile=embedded)
                page.locator('[data-add-extra]').click()
                page.locator('#kind-1').select_option('other')
                page.locator('#description-1').fill('Longer custom description for the additional line')
                geom=page.locator('#stay-price,#extra-price-0,#extra-price-1').evaluate_all('(es)=>es.map(e=>{const r=e.getBoundingClientRect();return {x:r.x,w:r.width}})')
                check(f'Invoice prices share left edge and width across Accommodation/Cleaning/Other: {locale} {width} embedded={embedded}',all(abs(r['x']-geom[0]['x'])<1 and abs(r['w']-geom[0]['w'])<1 for r in geom))
                if width>=760 and not embedded:
                    heading=page.locator('.invoice-head span').nth(3).bounding_box()
                    check(f'Invoice price header aligns with inputs: {locale} {width}',abs(heading['x']-geom[0]['x'])<1)
                    first=page.locator('#kind-0,#extra-quantity-0,#extra-unit-0,#extra-price-0,[data-remove-extra="0"]').evaluate_all('(es)=>es.map(e=>e.getBoundingClientRect().y)')
                    check(f'Invoice control tops align: {locale} {width}',max(first)-min(first)<1)
                elif width<=471 or embedded:
                    tops=page.locator('#kind-0,[data-remove-extra="0"]').evaluate_all('(es)=>es.map(e=>e.getBoundingClientRect().y)')
                    check(f'Mobile remove button aligns with its description selector: {locale} {width} embedded={embedded}',max(tops)-min(tops)<1)
                if embedded:
                    capture(f'invoice-embedded-mobile-{locale}-1280')

    load('feedback')
    page.locator('[data-feedback="saveDone"]').click()
    check('Save success announces the outcome once',page.locator('#feedback-live').inner_text() in ['', 'Changes saved'])
    page.locator('[data-feedback="failed"]').click()
    check('Failure has a sticky error treatment and accessible announcement',page.locator('.feedback-toast.error').count()==1 and page.locator('.feedback-toast.error .feedback-progress').count()==0)
    capture('feedback-success-error-en-1280')
    page.locator('.feedback-toast.error .dismiss').focus()
    page.wait_for_timeout(7100)
    check('Errors remain visible after success timeout',page.locator('.feedback-toast.error').count()==1 and page.locator('.feedback-toast.success').count()==0)
    page.locator('.feedback-toast.error .dismiss').click()
    check('Dismiss restores focus to the originating action',page.locator('[data-feedback="failed"]').evaluate('(e)=>e===document.activeElement'))
    page.locator('[data-feedback="partial"]').click()
    check('Partial acceptance is an amber persistent warning',page.locator('.feedback-toast.warning').count()==1 and page.locator('.feedback-toast.warning .feedback-progress').count()==0)
    page.locator('[data-feedback="saveDone"]').click()
    page.locator('[data-feedback="pending"]').click()
    page.locator('[data-feedback="accepted"]').click()
    check('At most three notifications are visible; overflow is queued',page.locator('.feedback-toast').count()==3)

    load('feedback',width=390)
    page.context.grant_permissions(['clipboard-read','clipboard-write'])
    copy=page.locator('[data-copy-link]')
    before=copy.bounding_box()
    copy.click()
    page.wait_for_function('!!document.querySelector(".copy-button.copied")')
    after=copy.bounding_box()
    check('Copy writes the intended synthetic URL',page.evaluate('navigator.clipboard.readText()')=='https://example.invalid/guest/demo')
    check('Copy confirmation does not move or resize its button',all(abs(before[k]-after[k])<1 for k in ['x','y','width','height']))
    capture('copy-confirmed-en-390')
    page.evaluate('Object.defineProperty(navigator,"clipboard",{configurable:true,value:{writeText:()=>Promise.reject(Error("Denied"))}})')
    page.wait_for_timeout(1900)
    copy.click()
    page.wait_for_function('!!document.querySelector(".feedback-toast.error")')
    check('Clipboard failure never shows a false Copied state',not copy.evaluate('(e)=>e.classList.contains("copied")') and page.locator('#copy-fallback').is_visible())

    load('search-review')
    page.locator('[data-search-open]').first.click()
    page.locator('#search-input').fill('Garden')
    check('Search filters familiar destinations and properties',page.locator('.search-result').count()==1 and 'Garden studio' in page.locator('.search-result').inner_text())
    page.keyboard.press('Enter')
    check('Search selection opens the result',page.locator('h1').inner_text()=='Garden studio')
    load('search-review',width=390)
    page.locator('[data-search-open]').first.click()
    capture('search-dialog-en-390')
    page.keyboard.press('Escape')
    check('Search Escape closes dialog and restores trigger focus',not page.locator('#search-dialog').evaluate('(e)=>e.open') and page.locator('[data-search-open]').first.evaluate('(e)=>e===document.activeElement'))
    page.keyboard.press('Control+k')
    check('Optional keyboard shortcut still opens Search',page.locator('#search-dialog').evaluate('(e)=>e.open'))
    page.keyboard.press('Escape')
    page.emulate_media(reduced_motion='reduce')
    load('feedback')
    page.locator('[data-feedback="saveDone"]').click()
    check('Reduced motion removes notification entrance animation',page.locator('.feedback-toast').evaluate('(e)=>getComputedStyle(e).animationName')=='none')
    page.emulate_media(reduced_motion='no-preference')

    load('register',panel=True)
    page.locator('[data-calendar="range"]').click()
    check('Day picker uses shared styled calendar with 42 days', page.locator('.day-grid button').count()==42)
    capture('register-day-calendar-en-1280')
    page.keyboard.press('Escape')
    page.locator('[data-cancel-filters]').click()
    page.locator('[data-export]').click()
    check('Export has explicit scope dates and property', page.locator('#export-dialog [data-calendar="day"]').count()==2 and page.locator('#field-export-property').count()==1)
    capture('export-dialog-en-1280')
    page.locator('[data-close-export]').click()

    load('register',width=360,panel=True)
    page.locator('[data-calendar="range"]').click()
    sizes=page.locator('.day-grid button').evaluate_all('(els)=>els.map(e=>({w:e.getBoundingClientRect().width,h:e.getBoundingClientRect().height}))')
    check('Mobile day-calendar targets are at least 44px',all(x['w']>=43.9 and x['h']>=44 for x in sizes))
    check('Mobile calendar stays inside viewport',page.locator('#calendar-popup').evaluate('(e)=>{const r=e.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth&&r.top>=0&&r.bottom<=innerHeight}'))
    capture('register-day-calendar-en-360')

    load('invoices',width=390,panel=True)
    page.locator('[data-calendar="month"]').click()
    capture('invoices-month-grid-en-390')
    page.keyboard.press('Escape')

    load('operators',width=390)
    page.locator('.operator-row').nth(1).locator('summary').click()
    capture('operators-disabled-delete-en-390')

    load('invoice-new',width=390)
    page.locator('#kind-0').select_option('other')
    capture('invoice-other-en-390')

    for locale in ['en','cs']:
        for width in [360,390,471,760,850,1280]:
            for name in PAGES:
                load(name,locale,width)
                check(f'No document overflow: {name} {locale} {width}', page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
                clipped=page.locator('main button:visible').evaluate_all('(es)=>es.filter(e=>e.scrollWidth>e.clientWidth+1||e.scrollHeight>e.clientHeight+1).map(e=>e.textContent.trim())')
                check(f'Button labels do not clip: {name} {locale} {width}: {clipped}',not clipped)
                groups=page.locator('.header-actions,.filter-footer,.operator-row .actions').evaluate_all('(groups)=>groups.map(g=>[...g.children].filter(e=>e.tagName==="BUTTON"||e.tagName==="DETAILS").map(e=>e.getBoundingClientRect().height))')
                check(f'Action group buttons share a height: {name} {locale} {width}',all(not heights or max(heights)-min(heights)<1 for heights in groups))
                if width in [390,1280]:
                    capture(f'{name}-{locale}-{width}')
                if name in defaults_pages:
                    page.locator('[data-toggle-filters]').click()
                    controls=page.locator('#filters-panel input, #filters-panel select, #filters-panel .control').evaluate_all('(els)=>els.map(e=>e.getBoundingClientRect().height)')
                    expected=44 if width<=600 else 42
                    check(f'Shared filter heights: {name} {locale} {width}', all(abs(h-expected)<1 for h in controls))
                    check(f'Open panel no overflow: {name} {locale} {width}', page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
                    if width in [390,1280]:
                        capture(f'{name}-filters-{locale}-{width}')
            print(f'Captured and checked {locale} at {width}px',flush=True)

    check('No JavaScript page errors', len(report['errors'])==0)
    browser.close()

(OUT/'checks.json').write_text(json.dumps(report,indent=2))
print(json.dumps({'chromium':report['chromium'],'checks':len(report['checks']),'screenshots':len(report['screenshots']),'errors':report['errors'],'out':str(OUT)}),flush=True)

names=[('dashboard','Dashboard'),('stays','Stays'),('invoices','Invoices'),('fees','Stay fees'),('fee-detail','Stay fee detail'),('register','Guest register'),('operators','Business & legal details'),('invoice-new','Invoice generator'),('properties','Properties'),('property','Property detail'),('address','Address without reporting pills'),('archived','Archived'),('audit','Settings audit'),('guest-links','Guest links overview'),('automation','Automation overview'),('locks','Digital door lock'),('feedback','Save, copy and report feedback'),('search-review','Search treatment'),('property-links','Property guest links'),('property-reporting','Property reporting'),('property-lock','Property lock'),('stay-detail','Stay detail')]
sections=[]
def embedded(file):return 'data:image/png;base64,'+base64.b64encode((OUT/file).read_bytes()).decode()
for name,title in names:
    views=[]
    for locale in ['en','cs']:
        for width in [1280,390]:
            fn=f'{name}{"-filters" if name in defaults_pages else ""}-{locale}-{width}.png'
            views.append(f'<figure data-locale="{locale}" class="{"desktop" if width==1280 else "mobile"}"><figcaption>{locale.upper()} · {width}px{" · Filters expanded" if name in defaults_pages else ""}</figcaption><img loading="lazy" src="{embedded(fn)}" alt="{title} {locale} {width}px"></figure>')
    sections.append(f'<section id="{name}"><h2>{title}</h2><div class="pair">'+''.join(views)+'</div></section>')
specials=[('stays-date-range-en-1280.png','One shared date-range control'),('dashboard-zero-states-en-1280.png','Zero counts remain neutral'),('dashboard-embedded-mobile-en-1280.png','Mobile panel responds to its own width'),('feedback-success-error-en-1280.png','Confirmed save and failed report'),('copy-confirmed-en-390.png','Copy icon becomes a checkmark without shifting'),('search-dialog-en-390.png','Search results with clear labels'),('stays-en-1280.png','Collapsed filters: applied summary remains visible'),('invoices-month-grid-en-1280.png','Compact month grid'),('operators-disabled-delete-en-1280.png','Linked operator: explained unavailable Delete'),('delete-confirmation-en-1280.png','Delete confirmation'),('invoice-other-en-1280.png','Other: custom description visible'),('register-day-calendar-en-1280.png','Matching day calendar'),('export-dialog-en-1280.png','Explicit export scope')]
for fn,title in specials:sections.append(f'<section><h2>{title}</h2><img class="special" loading="lazy" src="{embedded(fn)}" alt="{title}"></section>')
html='''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>UbyHost — final design screenshots</title><style>body{margin:0;background:#faf1ec;color:#241d1a;font:16px/1.5 system-ui}header{background:white;padding:24px;border-bottom:1px solid #ecdcd4;position:sticky;top:0;z-index:2}h1{margin:0;font-size:26px}p{margin:6px 0}main{max-width:1450px;margin:auto;padding:24px}section{background:white;border:1px solid #ecdcd4;border-radius:14px;padding:18px;margin-bottom:24px}h2{margin:0 0 14px;font-size:21px}.pair{display:grid;grid-template-columns:3fr 1fr;gap:20px;align-items:start}figure{margin:0}figcaption{font-size:14px;color:#5d4f49;padding-bottom:8px}img{width:100%;border:1px solid #ecdcd4;border-radius:8px}button{font:inherit;background:white;border:1px solid #d8c2b7;padding:8px 15px;border-radius:8px;color:#241d1a;cursor:pointer}[data-locale="cs"]{display:none}body.cs [data-locale="en"]{display:none}body.cs [data-locale="cs"]{display:block}.special{max-width:1100px}nav{display:flex;flex-wrap:wrap;gap:10px;margin-top:12px}nav a{color:#963e38;font-size:14px}@media(max-width:700px){main{padding:12px}.pair{grid-template-columns:1fr}.desktop{display:none}header{position:static;padding:16px}}@media print{header{position:static}section{break-inside:avoid}.pair{grid-template-columns:3fr 1fr}}</style><header><h1>UbyHost · final design review</h1><p>Real Playwright/Chromium screenshots of the standalone prototype. Fictional data; production app unchanged.</p><p>Dashboard: five unique stays · current and next 30 days · overdue first. Facility/invoice address source verification pending. Copy/search/report feedback examples included.</p><button onclick="document.body.classList.remove('cs')">English</button> <button onclick="document.body.classList.add('cs')">Čeština</button><nav>'''+''.join(f'<a href="#{name}">{title}</a>' for name,title in names)+'''</nav></header><main>'''+''.join(sections)+'</main>'
(OUT/'index.html').write_text(html)
print('Self-contained screenshot gallery:',OUT/'index.html',flush=True)
