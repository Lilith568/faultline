"""Opening the installer's landing page must never make a paid model request."""
import json
from urllib.parse import quote, urlsplit

import pytest
from playwright.async_api import async_playwright, expect


@pytest.mark.asyncio
@pytest.mark.parametrize('selected,expected', [
    ('composer', 'composer'),
    ('https://untrusted.invalid/target', 'profile'),
])
async def test_setup_landing_selects_only_bundled_demo_without_starting_hunt(server_url, selected, expected):
    starts = []

    async def api(route):
        if urlsplit(route.request.url).path == '/api/hunts':
            starts.append(route.request.post_data_json)
        await route.fulfill(status=200, content_type='application/json', body=json.dumps({
            'meta_configured': True, 'model': 'muse-spark-1.3', 'models': ['muse-spark-1.3'],
            'demo_apps': ['composer', 'profile'], 'recorded_demos': [],
        }))

    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page()
        await page.route('**/api/**', api)
        await page.goto(server_url + '/?demo=' + quote(selected, safe=''), wait_until='domcontentloaded')
        await expect(page.locator('#model')).to_contain_text('live calls required')
        await expect(page.locator('#url')).to_have_value(server_url + '/demo/' + expected + '.html?mode=buggy')
        await expect(page.locator('[data-demo="' + expected + '"]')).to_have_attribute('aria-pressed', 'true')
        if selected == 'composer':
            await expect(page.locator('#goal')).to_have_value(
                'Drafts must survive switching editor tabs and publishing must not submit twice.')
        assert starts == []
        await browser.close()
