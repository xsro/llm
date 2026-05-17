// 文件选择时显示文件名
document.getElementById('file').addEventListener('change', function(e) {
    const fileName = e.target.files[0]?.name || '';
    if (fileName) {
        console.log('Selected file:', fileName);
    }
});

// 知识库选择联动
document.getElementById('knowledge_id').addEventListener('change', function(e) {
    const customInput = document.getElementById('knowledge_id_custom');
    if (e.target.value === '') {
        customInput.style.display = 'block';
        customInput.focus();
    } else {
        customInput.style.display = 'none';
        customInput.value = '';
    }
});

// 表单提交时禁用按钮并显示进度
document.getElementById('uploadForm').addEventListener('submit', function(e) {
    const btn = document.getElementById('submitBtn');
    const progress = document.getElementById('progress');
    const progressText = document.getElementById('progressText');

    btn.disabled = true;
    btn.textContent = '⏳ 处理中...';
    progress.style.display = 'block';
    progressText.textContent = '正在转换 PDF，请耐心等待...';

    // 5秒后更新提示
    setTimeout(() => {
        progressText.textContent = '仍在处理中，请稍候...';
    }, 5000);
});

// 页面加载完成
document.addEventListener('DOMContentLoaded', function() {
    // 自动聚焦到文件选择
    document.getElementById('file').focus();
});
