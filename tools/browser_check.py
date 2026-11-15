"""Optional browser acceptance check: pip install playwright; install Chrome or Edge."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

root=Path(__file__).resolve().parents[1]
out=root/'runtime/screenshots';out.mkdir(parents=True,exist_ok=True)
errors=[];external=[];results=[]
with sync_playwright() as p:
    browser=p.chromium.launch(channel='msedge',headless=True)
    page=browser.new_page()
    page.on('pageerror',lambda e: errors.append(str(e)))
    page.on('request',lambda r: external.append(r.url) if not r.url.startswith(('http://127.0.0.1:8000','ws://127.0.0.1:8000','data:')) else None)
    for width,height in [(1280,800),(800,480),(390,844)]:
        page.set_viewport_size({'width':width,'height':height})
        for name in ['home','experiment','breadboard','analyzer','vic']:
            page.goto(f'http://127.0.0.1:8000/legacy#{name}')
            page.wait_for_selector('#connection.live')
            page.wait_for_timeout(200)
            if name=='analyzer':
                previous=page.request.get('http://127.0.0.1:8000/api/state').json()['capture_id']
                page.get_by_role('button',name='Single',exact=True).click()
                for _ in range(50):
                    current=page.request.get('http://127.0.0.1:8000/api/state').json()
                    if current['capture_id']!=previous and current['capture_status']=='complete': break
                    page.wait_for_timeout(50)
                assert current['capture_id']!=previous
                expect(page.locator('#capture-status')).to_have_text('complete')
                page.wait_for_timeout(100)
                page.get_by_role('button',name='Zoom in',exact=True).click()
            if name=='vic':
                if width==800:page.get_by_role('button',name='Dock',exact=True).click()
                page.get_by_role('button',name='Place on dock',exact=True).click()
                page.wait_for_timeout(200)
                assert 'Emulating 7400' in page.locator('#dock-state').inner_text()
                if width==800:page.get_by_role('button',name='Pinout',exact=True).click()
            overflow=page.evaluate('document.documentElement.scrollWidth > innerWidth')
            assert not overflow,(width,name,'horizontal page overflow')
            page.evaluate('window.scrollTo(0,0)')
            page.screenshot(path=str(out/f'{width}-{name}.png'),full_page=True)
            results.append({'width':width,'height':height,'page':name,'overflow':overflow})
    page.goto('http://127.0.0.1:8000/legacy#experiment');page.wait_for_selector('#connection.live')
    page.get_by_role('button',name='Simulator controls').click()
    page.select_option('#scenario','fault');page.select_option('#sim-input','2')
    page.get_by_role('button',name='Apply conditions').click()
    expect(page.locator('#observation')).to_contain_text('Y2: expected HIGH, measured LOW')
    page.set_viewport_size({'width':1280,'height':800})
    page.goto('http://127.0.0.1:8000/legacy#analyzer')
    page.wait_for_selector('#connection.live')
    while page.locator('[data-capture-ch]:checked').count():
        page.locator('[data-capture-ch]:checked').first.uncheck()
    for i in range(1,17):page.locator(f'[data-capture-ch="BB{i:02}A"]').check()
    page.select_option('#timebase','1000')
    assert int(page.locator('#rate').input_value())<=10000000
    page.get_by_role('button',name='Single',exact=True).click()
    page.wait_for_timeout(350)
    assert len(page.request.get('http://127.0.0.1:8000/api/capture').json()['ch'])==16
    page.evaluate('window.scrollTo(0,0)')
    page.screenshot(path=str(out/'1280-analyzer-16.png'),full_page=True)
    assert not errors,errors
    assert not external,external
    browser.close()
(root/'runtime/browser-results.json').write_text(json.dumps({'pages':results,'errors':errors,'external_requests':external},indent=2))
print(f'{len(results)} page/viewport checks passed; simulator controls passed; no JS errors or external requests.')
