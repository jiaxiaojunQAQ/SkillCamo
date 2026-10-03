const puppeteer = require('puppeteer-core');

/**
 * XHS Generic Monitor Script
 * --------------------------
 * Core Logic:
 * 1. Authenticates via XHS_COOKIE.
 * 2. Searches for a SINGLE specific keyword/phrase.
 * 3. Filters results by the last 7 days.
 * 4. Outputs structured report for further LLM analysis.
 */

(async () => {
  const executablePath = process.env.PUPPETEER_EXECUTABLE_PATH || 
                         (require('fs').existsSync('/usr/bin/chromium') ? '/usr/bin/chromium' : '/usr/bin/chromium-browser');

  const browser = await puppeteer.launch({
    executablePath: executablePath,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--headless=new']
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 1000 });
  await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36');
  
  const cookieString = process.env.XHS_COOKIE;
  if (!cookieString) {
    console.error('❌ Error: Environment variable XHS_COOKIE not found.');
    process.exit(1);
  }
  
  const cookies = cookieString.split(';').map(pair => {
    const [name, ...value] = pair.trim().split('=');
    return { name, value: value.join('='), domain: '.xiaohongshu.com', path: '/' };
  });
  await page.setCookie(...cookies);

  const query = process.argv[2];
  if (!query) {
    console.error('Usage: node generic_monitor.js "Your Search Query"');
    process.exit(1);
  }

  const allMatches = [];
  const seenIds = new Set();

  const targetUrl = `https://www.xiaohongshu.com/search_result?keyword=${encodeURIComponent(query)}&source=web_search_result_notes&sort=time_descending`;
  
  try {
    await page.goto(targetUrl, { waitUntil: 'networkidle2' });
    for (let i = 0; i < 4; i++) {
      await page.evaluate(() => window.scrollBy(0, 1200));
      await new Promise(r => setTimeout(r, 1200));
    }

    const results = await page.evaluate(() => {
      return Array.from(document.querySelectorAll('section.note-item')).map(item => {
          const title = item.querySelector('.title')?.innerText || '';
          const author = item.querySelector('.name')?.innerText || '';
          const dateStr = item.querySelector('.time')?.innerText || '';
          const likes = item.querySelector('.count')?.innerText || '0';
          const linkEl = item.querySelector('a.cover') || item.querySelector('a');
          let rawHref = linkEl?.getAttribute('href') || '';
          const idMatch = rawHref.match(/\/(?:search_result|explore|note)\/([a-zA-Z0-9]+)/) || rawHref.match(/\/([a-zA-Z0-9]{24,})/);
          const id = idMatch ? idMatch[1] : '';
          return { id, title, author, dateStr, likes };
      });
    });

    results.forEach(n => {
      if (!n.id || seenIds.has(n.id)) return;
      let isRecent = false;
      
      const today = new Date();
      const yesterday = new Date(today);
      yesterday.setDate(today.getDate() - 1);
      
      const formatDate = (date) => {
          const m = (date.getMonth() + 1).toString().padStart(2, '0');
          const d = date.getDate().toString().padStart(2, '0');
          return `${m}-${d}`;
      };
      
      const todayStr = formatDate(today);
      const yesterdayStr = formatDate(yesterday);

      if (/刚刚|分钟前|小时前|昨天|今天/.test(n.dateStr)) {
          isRecent = true;
      } else if (n.dateStr.includes(todayStr) || n.dateStr.includes(yesterdayStr)) {
          isRecent = true;
      } else {
          const dayMatch = n.dateStr.match(/(\d+)天前/);
          if (dayMatch && parseInt(dayMatch[1]) <= 7) isRecent = true;
      }

      if (isRecent) {
          seenIds.add(n.id);
          allMatches.push(n);
      }
    });
  } catch (e) {
    console.error(`Error during scan: ${e.message}`);
  }

  const crawlTime = new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' });
  let report = `🔍 **XHS Generic Monitor: "${query}"**\n`;
  report += `Generated: ${crawlTime} | Found: ${allMatches.length}\n\n`;

  if (allMatches.length > 0) {
    allMatches.slice(0, 20).forEach((n, i) => {
      report += `${i+1}. [${n.title || 'No Title'}]\n`;
      report += `   • Date: ${n.dateStr} | Author: ${n.author} (${n.likes} likes)\n`;
      report += `   • Link: https://www.xiaohongshu.com/explore/${n.id}\n`;
    });
  } else {
    report += `--- No recent posts found for this query ---`;
  }

  process.stdout.write(report);
  await browser.close();
})();
