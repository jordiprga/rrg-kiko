import { test, expect } from '@playwright/test';

test('real RUT case hides the future, reveals it and restores its shared URL under Pages', async ({page}, testInfo) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('./?sv=1&stf=weekly&symbol=RUT&rule=lagging-improving&study=case#estrategias');
  await expect(page.getByRole('heading', { name: '¿Qué aportan estos giros?' })).toBeVisible();
  await expect(page.locator('#study-case-status')).toContainText('hasta 2025-06-06');
  await expect(page.getByRole('button', { name: 'Ver qué pasó después' })).toBeVisible();
  const beforeMax = await page.locator('#study-cursor').getAttribute('max');
  await page.screenshot({path: testInfo.outputPath('case-before.png'), fullPage:true});
  await page.getByRole('button', { name: 'Ver qué pasó después' }).click();
  await expect(page.locator('#study-case-status')).toContainText('Evolución del cierre');
  expect(Number(await page.locator('#study-cursor').getAttribute('max'))).toBeGreaterThan(Number(beforeMax));
  const shared = page.url();
  expect(shared).toContain('/rrg-kiko/');
  expect(shared).toMatch(/case=[a-f0-9]{24}/);
  await page.reload();
  await expect(page.locator('#study-case-status')).toContainText('Futuro oculto');
  await expect(page.locator('#study-case-status')).toContainText('2025-06-06');
  await page.locator('.strategy-zones summary').click();
  await expect(page.locator('#study-percentiles')).toContainText('4 activos');
  await expect(page.locator('.strategy-zone-grid .current')).toHaveText('RUT');
  await page.screenshot({path:testInfo.outputPath('case-zones.png'),fullPage:true});
  expect(errors).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy();
});

test('coverage blocks stock conclusions and failed clipboard offers a usable URL', async ({page}, testInfo) => {
  await page.addInitScript(() => Object.defineProperty(navigator, 'clipboard', { configurable:true, value:{writeText:async()=>{throw new Error('denied');}} }));
  await page.goto('./#estrategias');
  await page.locator('#study-universe').selectOption('stocks');
  await expect(page.getByRole('heading', {name:'Universo todavía no evaluable'})).toBeVisible();
  await expect(page.locator('.strategy-coverage').first()).toContainText('848 tickers');
  await page.getByRole('button', {name:'Resultados', exact:true}).click();
  await expect(page.getByRole('heading', {name:'Todavía no podemos medir la ventaja en el S&P 500 histórico'})).toBeVisible();
  await expect(page.locator('.strategy-metrics')).toContainText('Sin conclusión');
  await page.getByRole('button', {name:'Copiar este estudio'}).click();
  await expect(page.getByRole('textbox', {name:'Enlace del estudio'})).toHaveValue(/universe=stocks/);
  await page.screenshot({path:testInfo.outputPath('stock-coverage.png'),fullPage:true});
});

test('three main tabs support keyboard and preserve explorer settings', async ({page}) => {
  await page.goto('./?v=1&g=indices&tf=weekly&b=GSPC&s=RUT,IXIC&tail=30');
  await page.getByRole('tab', {name:'Explorar mercado'}).focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.getByRole('tab', {name:'Estrategias'})).toHaveAttribute('aria-selected','true');
  await expect(page.locator('#study-universe')).toBeVisible();
  await page.getByRole('tab', {name:'Estrategias'}).focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.getByRole('tab', {name:'Qué he hecho'})).toHaveAttribute('aria-selected','true');
  await page.keyboard.press('Home');
  await expect(page.getByRole('tab', {name:'Explorar mercado'})).toHaveAttribute('aria-selected','true');
  expect(new URL(page.url()).searchParams.get('tail')).toBe('30');
});
