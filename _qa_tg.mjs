 export default async function run(page, ui) {
  const out = {};

  // Wait for chats to render, then click the first real chat.
  await page.waitForSelector('#chat-list > div[onclick]', { timeout: 20000 });
  const snap = await ui.snapshot();
  out.chatRows = (snap.match(/@e\d+/g) || []).length;

  await page.locator('#chat-list > div[onclick]').first().click();
  await page.waitForTimeout(1500);

  out.activeChatTitle = await page.locator('#active-chat-title').innerText();
  out.bubbleCount = await page.evaluate(
    () => document.querySelectorAll('#messages-container .bubble-in, #messages-container .bubble-out').length
  );
  out.incomingBubbles = await page.evaluate(
    () => document.querySelectorAll('#messages-container .bubble-in').length
  );
  out.outgoingBubbles = await page.evaluate(
    () => document.querySelectorAll('#messages-container .bubble-out').length
  );
  out.bubbleInBg = await page.evaluate(() => {
    const el = document.querySelector('#messages-container .bubble-in');
    return el ? getComputedStyle(el).backgroundImage + ' | ' + getComputedStyle(el).backgroundColor : null;
  });
  out.bubbleOutBg = await page.evaluate(() => {
    const el = document.querySelector('#messages-container .bubble-out');
    return el ? getComputedStyle(el).backgroundImage + ' | ' + getComputedStyle(el).backgroundColor : null;
  });

  // Proxy pill popup (small badge modal) must open.
  const pill = snap.match(/@(e\d+) button[^\n]*"Proxy: Auto/)?.[1];
  out.proxyPillRef = pill || null;
  if (pill) {
    await ui.click(pill);
    await page.waitForTimeout(1200);
    out.proxyModalVisible = await page.evaluate(
      () => !document.getElementById('proxy-modal').classList.contains('hidden')
    );
    out.proxyModalHasAddForm = await page.evaluate(() => !!document.getElementById('add-proxy-form'));
    out.proxyModalHasRefresh = await page.evaluate(() => !!document.getElementById('refresh-proxies-btn'));
    out.proxyNodeRows = await page.evaluate(
      () => document.querySelectorAll('#proxy-list-items > div').length
    );
    await page.evaluate(() => document.getElementById('proxy-modal').classList.add('hidden'));
  }

  // Right profile panel content
  out.profileTitle = await page.locator('#profile-title').innerText();
  out.membersRendered = await page.evaluate(
    () => document.querySelectorAll('#profile-members-list > div').length
  );

  return out;
}
