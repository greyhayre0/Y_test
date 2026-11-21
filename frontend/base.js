document.addEventListener('DOMContentLoaded', () => {
    const API_URL = 'http://127.0.0.1:8000';
    
    // 1. Сворачивание сайдбара
    document.getElementById('toggle-sidebar-btn').addEventListener('click', () => {
        document.body.classList.toggle('sidebar-collapsed');
    });

    // 2. Проверка авторизации
    const token = localStorage.getItem('token');
    const headerRight = document.getElementById('header-right');
    
    if (!token) {
        headerRight.innerHTML = `<button class="create-btn" onclick="window.location.href='/login'">Войти</button>`;
    } else {
        headerRight.innerHTML = `
            <button class="create-btn" id="btn-create"><i class="ph ph-plus"></i> Создать</button>
            <div class="avatar" style="margin-left: 16px;"></div>
        `;
        document.getElementById('btn-create').addEventListener('click', () => {
            document.getElementById('upload-modal').style.display = 'flex';
        });
    }

    // 3. РОУТИНГ (Встраивание контента)
    const contentArea = document.getElementById('app-content');
    const currentPath = window.location.pathname;
    const urlParams = new URLSearchParams(window.location.search);

    if (currentPath === '/' || currentPath === '/index.html') {
        // Грузим главную (ленту)
        fetch('/frontend/pages/home.html')
            .then(res => res.text())
            .then(html => {
                contentArea.innerHTML = html;
                loadVideos(); // Вызываем функцию загрузки видео
            });
    } 
    else if (currentPath === '/video') {
        // Грузим страницу видео
        const videoId = urlParams.get('id');
        fetch('/frontend/pages/video.html')
            .then(res => res.text())
            .then(html => {
                contentArea.innerHTML = html;
                loadVideoPage(videoId); // Вызываем функцию загрузки конкретного видео
            });
    }
    else if (currentPath === '/login') {
         // Грузим логин (если сделаете)
         contentArea.innerHTML = `<h2>Страница входа в разработке</h2>`;
    }

    // ================= ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =================

    // Загрузка видео для главной
    async function loadVideos() {
        const grid = document.getElementById('video-grid');
        if (!grid) return;
        try {
            const res = await fetch(`${API_URL}/videos`);
            const videos = await res.json();
            if (videos.length === 0) {
                grid.innerHTML = '<p style="color: #aaa;">Видео пока нет.</p>';
                return;
            }
            grid.innerHTML = videos.map(v => `
                <div class="video-card" onclick="window.location.href='/video?id=${v.id}'">
                    <div class="thumbnail">
                        <img src="https://images.unsplash.com/photo-1611162617474-5b21e879e113?auto=format&fit=crop&w=600&q=80" style="width:100%; height:100%; object-fit:cover;">
                    </div>
                    <div class="video-info">
                        <h3>${v.title}</h3>
                        <p class="stats">Автор #${v.owner_id}</p>
                    </div>
                </div>
            `).join('');
        } catch (e) {
            grid.innerHTML = '<p style="color: red;">Ошибка загрузки</p>';
        }
    }

    // Логика модалки загрузки (глобальная)
    document.getElementById('close-modal-btn').addEventListener('click', () => {
        document.getElementById('upload-modal').style.display = 'none';
    });
    document.getElementById('select-file-btn').addEventListener('click', () => {
        document.getElementById('file-input').click();
    });
    document.getElementById('file-input').addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            document.getElementById('upload-form').style.display = 'block';
            document.getElementById('select-file-btn').style.display = 'none';
        }
    });
    document.getElementById('submit-upload-btn').addEventListener('click', async () => {
        const file = document.getElementById('file-input').files[0];
        const title = document.getElementById('upload-title').value;
        if (!file || !title) return alert('Выберите файл и укажите название');

        const formData = new FormData();
        formData.append('file', file);
        formData.append('title', title);
        formData.append('description', '');

        try {
            const res = await fetch(`${API_URL}/videos`, { method: 'POST', body: formData });
            if (res.ok) {
                alert('Успешно!');
                document.getElementById('upload-modal').style.display = 'none';
                window.location.reload(); // Перезагружаем страницу, чтобы увидеть новое видео
            } else {
                alert('Ошибка при загрузке');
            }
        } catch (e) {
            alert('Ошибка сети');
        }
    });
});