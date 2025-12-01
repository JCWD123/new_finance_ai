// 共享的工具函数
function formatDate(dateStr) {
  const date = new Date(dateStr);
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  });
}

// 新闻相关函数
async function fetchNewsDetail(newsId) {
  try {
    const response = await fetch(`/api/news/${newsId}`);
    if (!response.ok) {
      throw new Error('新闻获取失败');
    }
    const data = await response.json();
    showNewsDetail(data);
  } catch (error) {
    console.error('获取新闻详情失败:', error);
  }
}

function showNewsDetail(news) {
  const modal = document.getElementById('newsDetailModal');
  if (!modal) {
    console.error('找不到新闻详情弹窗元素');
    return;
  }

  const header = modal.querySelector('.news-detail-header');
  const content = modal.querySelector('.news-detail-content');
  const score = typeof news.score === 'number' ? news.score.toFixed(1) : '暂无';

  // 先更新内容
  header.querySelector('.news-score').textContent = `评分: ${score}`;
  content.querySelector('.news-content').innerHTML = `
    <div class="news-content">
      ${news.content}
    </div>
    ${news.links ? `
      <div class="news-links">
        <h4>相关链接</h4>
        ${Array.isArray(news.links) ? news.links.map(link =>
          `<a href="${link}" target="_blank">
            <svg style="width:16px;height:16px;vertical-align:middle;margin-right:8px" viewBox="0 0 24 24">
              <path fill="currentColor" d="M14,3V5H17.59L7.76,14.83L9.17,16.24L19,6.41V10H21V3M19,19H5V5H12V3H5C3.89,3 3,3.9 3,5V19A2,2 0 0,0 5,21H19A2,2 0 0,0 21,19V12H19V19Z" />
            </svg>
            ${new URL(link).hostname}
          </a>`
        ).join('') : '<p>暂无相关链接</p>'}
      </div>
    ` : ''}
  `;

  // 使用 requestAnimationFrame 确保 DOM 更新后再添加 active 类
  requestAnimationFrame(() => {
    modal.classList.add('active');
    // 为 body 添加禁止滚动类
    document.body.style.overflow = 'hidden';
  });
}

function closeNewsDetail() {
  const modal = document.getElementById('newsDetailModal');
  if (!modal) return;
  
  modal.classList.remove('active');
  // 移除 body 的禁止滚动
  document.body.style.overflow = '';
  
  // 等待过渡动画完成后重置滚动位置
  setTimeout(() => {
    if (modal.querySelector('.news-detail-content')) {
      modal.querySelector('.news-detail-content').scrollTop = 0;
    }
  }, 300);
}

// 更新侧边栏新闻列表
function updateSidebarNews(news) {
  const sidebarNewsList = document.getElementById('sidebarNewsList');
  sidebarNewsList.innerHTML = news.map(item => `
    <div class="news-item-sidebar" onclick="fetchNewsDetail('${item.id}')">
      <h4>${item.event_summary}</h4>
      <div class="news-date">${formatDate(item.date)}</div>
    </div>
  `).join('');
}

// 绑定事件引用点击事件
function bindEventReferences() {
  document.querySelectorAll('.event-reference').forEach(ref => {
    ref.addEventListener('click', (e) => {
      const newsId = e.target.getAttribute('data-news-id');
      if (newsId) {
        fetchNewsDetail(newsId);
      }
    });
  });
}
