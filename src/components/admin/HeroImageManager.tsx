import { useState, useEffect, useCallback, useRef } from "react";
import { LogOut, RefreshCw, Plus, Upload, X, Check, Image, AlertTriangle } from "lucide-react";
import { adminApi, HeroImage } from "../../services/adminApi";

interface HeroImageManagerProps {
  onLogout: () => void;
}

const MAX_IMAGES = 8;
const MIN_IMAGES = 1;

export function HeroImageManager({ onLogout }: HeroImageManagerProps) {
  const [images, setImages] = useState<HeroImage[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  // 確認彈窗狀態
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [confirmAction, setConfirmAction] = useState<'upload' | 'replace' | null>(null);

  const fetchImages = useCallback(async (selectLast = false) => {
    setIsLoading(true);
    setError("");

    try {
      const result = await adminApi.getHeroImages();
      if (result.success && result.images) {
        setImages(result.images);
        if (selectLast && result.images.length > 0) {
          // 選擇最後一張（用於新上傳後）
          setActiveTab(result.images.length - 1);
        } else if (result.images.length > 0) {
          // 確保 activeTab 不超出範圍
          setActiveTab(prev => Math.min(prev, result.images.length - 1));
        }
      } else {
        setError(result.error || "無法載入圖片");
      }
    } catch {
      setError("網路錯誤");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchImages();
  }, []);

  // 清理 previewUrl 以防止 memory leak
  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  const currentImage = images[activeTab];
  const isNewSlot = activeTab >= images.length;
  const canAddMore = images.length < MAX_IMAGES;
  const canDelete = images.length > MIN_IMAGES;

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const validTypes = ["image/jpeg", "image/png", "image/webp"];
    if (!validTypes.includes(file.type)) {
      setError("只支援 JPG、PNG、WebP 格式");
      return;
    }

    if (file.size > 5 * 1024 * 1024) {
      setError("檔案大小不能超過 5MB");
      return;
    }

    setSelectedFile(file);
    setPreviewUrl(URL.createObjectURL(file));
    setError("");
  };

  // 顯示上傳確認彈窗
  const handleUploadClick = () => {
    if (!selectedFile) return;
    setConfirmAction('upload');
    setShowConfirmModal(true);
  };

  // 顯示替換確認彈窗
  const handleReplaceClick = () => {
    if (!selectedFile || !currentImage) return;
    setConfirmAction('replace');
    setShowConfirmModal(true);
  };

  // 確認後執行上傳
  const handleConfirmAction = async () => {
    setShowConfirmModal(false);

    if (confirmAction === 'upload') {
      await executeUpload();
    } else if (confirmAction === 'replace') {
      await executeReplace();
    }

    setConfirmAction(null);
  };

  // 取消確認
  const handleCancelConfirm = () => {
    setShowConfirmModal(false);
    setConfirmAction(null);
  };

  // 實際執行上傳
  const executeUpload = async () => {
    if (!selectedFile) return;

    setIsUploading(true);
    setError("");

    try {
      const result = await adminApi.uploadImage(selectedFile, `輪播 ${images.length + 1}`);
      if (result.success) {
        // 清理預覽 URL
        if (previewUrl) {
          URL.revokeObjectURL(previewUrl);
        }
        setSelectedFile(null);
        setPreviewUrl(null);
        // 重新載入圖片並選擇最後一張
        await fetchImages(true);
      } else {
        setError(result.error || "上傳失敗");
      }
    } catch {
      setError("上傳失敗");
    } finally {
      setIsUploading(false);
    }
  };

  // 實際執行替換
  const executeReplace = async () => {
    if (!selectedFile || !currentImage) return;

    setIsUploading(true);
    setError("");

    try {
      await adminApi.deleteImage(currentImage.id);
      const result = await adminApi.uploadImage(selectedFile, currentImage.alt_text || `輪播 ${activeTab + 1}`);
      if (result.success) {
        // 清理預覽 URL
        if (previewUrl) {
          URL.revokeObjectURL(previewUrl);
        }
        setSelectedFile(null);
        setPreviewUrl(null);
        await fetchImages();
      } else {
        setError(result.error || "替換失敗");
      }
    } catch {
      setError("替換失敗");
    } finally {
      setIsUploading(false);
    }
  };

  const handleDelete = async () => {
    if (!currentImage || !canDelete) return;

    if (!confirm("確定要刪除這張輪播圖嗎？")) return;

    setIsLoading(true);
    try {
      const result = await adminApi.deleteImage(currentImage.id);
      if (result.success) {
        await fetchImages();
        if (activeTab > 0) {
          setActiveTab(activeTab - 1);
        }
      } else {
        setError(result.error || "刪除失敗");
      }
    } catch {
      setError("刪除失敗");
    } finally {
      setIsLoading(false);
    }
  };

  const handleAddNewSlot = () => {
    if (canAddMore) {
      setActiveTab(images.length);
      setSelectedFile(null);
      setPreviewUrl(null);
    }
  };

  const cancelPreview = () => {
    // 清理預覽 URL
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
    setSelectedFile(null);
    setPreviewUrl(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
    if (isNewSlot && images.length > 0) {
      setActiveTab(images.length - 1);
    }
  };

  const handleLogout = async () => {
    await adminApi.logout();
    onLogout();
  };

  const displayTabs = isNewSlot ? images.length + 1 : images.length;

  return (
    <div className="min-h-screen" style={{ backgroundColor: '#f8fafc' }}>
      {/* Header */}
      <header style={{ backgroundColor: '#ffffff', borderBottom: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold" style={{ color: '#1e293b' }}>
              Hero Banner 管理
            </h1>
            <p className="text-sm" style={{ color: '#64748b' }}>桃園市政府青年事務局</p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => fetchImages()}
              disabled={isLoading}
              className="p-2.5 rounded-lg transition-all disabled:opacity-50"
              style={{ color: '#64748b', backgroundColor: isLoading ? '#f1f5f9' : 'transparent' }}
              title="重新整理"
            >
              <RefreshCw size={20} className={isLoading ? "animate-spin" : ""} />
            </button>
            <button
              onClick={handleLogout}
              className="flex items-center gap-2 px-4 py-2 rounded-lg transition-all"
              style={{ color: '#64748b', backgroundColor: '#f1f5f9' }}
            >
              <LogOut size={18} />
              <span className="text-sm font-medium">登出</span>
            </button>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-5xl mx-auto px-6 py-8">
        {error && (
          <div className="mb-6 p-4 rounded-xl flex items-center justify-between" style={{ backgroundColor: '#fef2f2', border: '1px solid #fecaca' }}>
            <span style={{ color: '#dc2626' }}>{error}</span>
            <button onClick={() => setError("")} style={{ color: '#f87171' }}>
              <X size={18} />
            </button>
          </div>
        )}

        {/* 主要內容區 - 卡片式設計 */}
        <div className="rounded-2xl overflow-hidden" style={{ backgroundColor: '#ffffff', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -2px rgba(0,0,0,0.1)' }}>
          {/* 卡片標題 */}
          <div className="px-6 py-4" style={{ borderBottom: '1px solid #e2e8f0', backgroundColor: '#f8fafc' }}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ backgroundColor: '#f97316' }}>
                  <Image size={20} style={{ color: '#ffffff' }} />
                </div>
                <div>
                  <h2 className="font-semibold" style={{ color: '#1e293b' }}>輪播圖片管理</h2>
                  <p className="text-sm" style={{ color: '#64748b' }}>
                    正在編輯：輪播 {activeTab + 1} / {Math.max(displayTabs, 1)}
                  </p>
                </div>
              </div>
              <div className="px-3 py-1.5 rounded-full text-sm font-medium" style={{ backgroundColor: '#fff7ed', color: '#ea580c' }}>
                {images.length} / {MAX_IMAGES} 張
              </div>
            </div>
          </div>

          <div className="flex">
            {/* 左側 - 輪播列表 */}
            <div className="w-48 p-4" style={{ borderRight: '1px solid #e2e8f0', backgroundColor: '#fafafa' }}>
              <p className="text-xs font-medium mb-3 px-2" style={{ color: '#94a3b8' }}>輪播列表</p>
              <div className="space-y-2">
                {/* 現有圖片的 tabs */}
                {images.map((img, index) => {
                  const isActive = activeTab === index;
                  return (
                    <button
                      key={img.id}
                      onClick={() => {
                        setActiveTab(index);
                        setSelectedFile(null);
                        setPreviewUrl(null);
                      }}
                      style={{
                        backgroundColor: isActive ? '#f97316' : '#ffffff',
                        color: isActive ? '#ffffff' : '#374151',
                        border: isActive ? 'none' : '1px solid #e5e7eb',
                        boxShadow: isActive ? '0 4px 6px -1px rgba(249, 115, 22, 0.3)' : '0 1px 2px rgba(0,0,0,0.05)',
                      }}
                      className="w-full px-4 py-3 rounded-xl text-left transition-all hover:scale-[1.02]"
                    >
                      <span className="font-medium text-sm">輪播 {index + 1}</span>
                    </button>
                  );
                })}

                {/* 新增 tab（如果正在新增） */}
                {isNewSlot && (
                  <button
                    style={{
                      backgroundColor: '#f97316',
                      color: '#ffffff',
                      boxShadow: '0 4px 6px -1px rgba(249, 115, 22, 0.3)',
                    }}
                    className="w-full px-4 py-3 rounded-xl text-left"
                  >
                    <span className="font-medium text-sm">輪播 {images.length + 1}</span>
                  </button>
                )}

                {/* 新增按鈕 */}
                {canAddMore && images.length > 0 && !isNewSlot && (
                  <button
                    onClick={handleAddNewSlot}
                    style={{
                      backgroundColor: '#ffffff',
                      border: '2px dashed #93c5fd',
                    }}
                    className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl transition-all hover:bg-blue-50"
                  >
                    <Plus size={16} style={{ color: '#3b82f6' }} />
                    <span className="text-sm font-medium" style={{ color: '#3b82f6' }}>新增輪播</span>
                  </button>
                )}
              </div>
            </div>

            {/* 右側 - 圖片編輯區 */}
            <div className="flex-1 p-6">
              {/* 圖片預覽區 - 固定比例容器 */}
              <div className="mb-6">
                <p className="text-sm font-medium mb-3" style={{ color: '#374151' }}>圖片預覽</p>
                <div
                  className="relative rounded-xl overflow-hidden"
                  style={{
                    backgroundColor: '#f1f5f9',
                    aspectRatio: '16/9',
                    maxHeight: '320px',
                  }}
                >
                  {previewUrl ? (
                    <div className="relative w-full h-full group">
                      <img
                        src={previewUrl}
                        alt="預覽"
                        className="w-full h-full object-cover"
                      />
                      <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity">
                        <div className="absolute bottom-4 left-4 right-4 flex items-center justify-between">
                          <span className="px-3 py-1.5 rounded-lg text-sm font-medium" style={{ backgroundColor: '#3b82f6', color: '#ffffff' }}>
                            新圖片預覽
                          </span>
                          <button
                            onClick={cancelPreview}
                            className="p-2 rounded-lg transition-all"
                            style={{ backgroundColor: 'rgba(255,255,255,0.9)', color: '#374151' }}
                          >
                            <X size={18} />
                          </button>
                        </div>
                      </div>
                    </div>
                  ) : currentImage && !isNewSlot ? (
                    <div className="relative w-full h-full">
                      <img
                        src={currentImage.url}
                        alt={currentImage.alt_text || "輪播圖片"}
                        className="w-full h-full object-cover"
                      />
                      <div className="absolute bottom-0 left-0 right-0 p-4" style={{ background: 'linear-gradient(to top, rgba(0,0,0,0.6), transparent)' }}>
                        <span className="text-white text-sm font-medium">
                          {currentImage.alt_text || `輪播 ${activeTab + 1}`}
                        </span>
                      </div>
                    </div>
                  ) : (
                    <div className="w-full h-full flex flex-col items-center justify-center gap-3">
                      <div className="w-16 h-16 rounded-full flex items-center justify-center" style={{ backgroundColor: '#e2e8f0' }}>
                        <Image size={32} style={{ color: '#94a3b8' }} />
                      </div>
                      <p style={{ color: '#94a3b8' }}>尚未選擇圖片</p>
                    </div>
                  )}
                </div>
              </div>

              {/* 上傳區域 */}
              <div className="space-y-4">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  onChange={handleFileSelect}
                  className="hidden"
                  id="imageUpload"
                />

                <label
                  htmlFor="imageUpload"
                  className="flex items-center justify-center gap-3 w-full py-4 rounded-xl cursor-pointer transition-all"
                  style={{
                    border: '2px dashed #cbd5e1',
                    backgroundColor: '#f8fafc',
                    color: '#64748b',
                  }}
                >
                  <Upload size={20} />
                  <span className="font-medium">點擊上傳圖片</span>
                </label>

                {/* 格式說明 */}
                <div className="flex items-center gap-6 text-sm" style={{ color: '#94a3b8' }}>
                  <span>• 支援 JPG、PNG、WebP</span>
                  <span>• 最大 5 MB</span>
                  <span>• 建議比例 16:9</span>
                </div>

                {/* 操作按鈕 */}
                {selectedFile && (
                  <div className="flex gap-3 pt-2">
                    {isNewSlot ? (
                      <button
                        onClick={handleUploadClick}
                        disabled={isUploading}
                        className="flex-1 flex items-center justify-center gap-2 py-3 rounded-xl font-medium transition-all disabled:opacity-50"
                        style={{ backgroundColor: '#3b82f6', color: '#ffffff' }}
                      >
                        {isUploading ? (
                          <RefreshCw size={18} className="animate-spin" />
                        ) : (
                          <Check size={18} />
                        )}
                        <span>{isUploading ? "上傳中..." : "發布上傳"}</span>
                      </button>
                    ) : (
                      <button
                        onClick={handleReplaceClick}
                        disabled={isUploading}
                        className="flex-1 flex items-center justify-center gap-2 py-3 rounded-xl font-medium transition-all disabled:opacity-50"
                        style={{ backgroundColor: '#f97316', color: '#ffffff' }}
                      >
                        {isUploading ? (
                          <RefreshCw size={18} className="animate-spin" />
                        ) : (
                          <Check size={18} />
                        )}
                        <span>{isUploading ? "替換中..." : "發布替換"}</span>
                      </button>
                    )}
                    <button
                      onClick={cancelPreview}
                      disabled={isUploading}
                      className="px-6 py-3 rounded-xl font-medium transition-all disabled:opacity-50"
                      style={{ backgroundColor: '#f1f5f9', color: '#64748b' }}
                    >
                      取消
                    </button>
                  </div>
                )}

                {/* 刪除按鈕 */}
                {!isNewSlot && currentImage && canDelete && !selectedFile && (
                  <button
                    onClick={handleDelete}
                    disabled={isLoading}
                    className="w-full py-3 rounded-xl font-medium transition-all disabled:opacity-50"
                    style={{
                      backgroundColor: '#fef2f2',
                      color: '#dc2626',
                      border: '1px solid #fecaca',
                    }}
                  >
                    刪除此輪播圖
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* 底部提示 */}
          <div className="px-6 py-4 text-center text-sm" style={{ borderTop: '1px solid #e2e8f0', backgroundColor: '#f8fafc', color: '#94a3b8' }}>
            輪播圖會自動在首頁顯示，每 5 秒切換一次
          </div>
        </div>
      </main>

      {/* 確認發布彈窗 */}
      {showConfirmModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          {/* 背景遮罩 */}
          <div
            className="absolute inset-0"
            style={{ backgroundColor: 'rgba(0, 0, 0, 0.5)', zIndex: 0 }}
            onClick={handleCancelConfirm}
          />

          {/* 彈窗內容 */}
          <div
            className="bg-white rounded-2xl shadow-2xl overflow-hidden"
            style={{
              animation: 'fadeIn 0.2s ease-out',
              zIndex: 10,
              position: 'relative',
              width: '90vw',
              maxWidth: '700px',
              margin: '0 16px'
            }}
          >
            {/* 頂部警告條 */}
            <div className="px-6 py-4 flex items-center gap-3" style={{ backgroundColor: '#fef3c7' }}>
              <div className="w-10 h-10 rounded-full flex items-center justify-center" style={{ backgroundColor: '#f59e0b' }}>
                <AlertTriangle size={20} style={{ color: '#ffffff' }} />
              </div>
              <div>
                <h3 className="font-semibold" style={{ color: '#92400e' }}>
                  確認{confirmAction === 'upload' ? '上傳' : '替換'}
                </h3>
                <p className="text-sm" style={{ color: '#a16207' }}>
                  請確認圖片無誤後再發布
                </p>
              </div>
            </div>

            {/* 預覽圖片 - 模擬首頁 Hero Banner 顯示效果 */}
            <div className="px-6 py-4">
              <p className="text-sm font-medium mb-2" style={{ color: '#374151' }}>首頁顯示預覽：</p>
              <p className="text-xs mb-3" style={{ color: '#94a3b8' }}>以下為圖片在首頁 Hero 區域的實際顯示比例（1920×600）</p>
              {previewUrl && (
                <div
                  className="rounded-xl overflow-hidden border"
                  style={{
                    aspectRatio: '1920/600',
                    backgroundColor: '#f1f5f9',
                    borderColor: '#e2e8f0',
                    width: '100%'
                  }}
                >
                  <img
                    src={previewUrl}
                    alt="預覽"
                    style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                  />
                </div>
              )}
              <p className="mt-3 text-sm" style={{ color: '#64748b' }}>
                {confirmAction === 'upload'
                  ? `此圖片將新增為輪播 ${images.length + 1}，並立即在首頁顯示。`
                  : `此圖片將替換輪播 ${activeTab + 1}，並立即在首頁顯示。`
                }
              </p>
            </div>

            {/* 按鈕區 */}
            <div className="px-6 py-4 flex gap-3" style={{ backgroundColor: '#f8fafc', borderTop: '1px solid #e2e8f0' }}>
              <button
                onClick={handleCancelConfirm}
                className="flex-1 py-3 rounded-xl font-medium transition-all"
                style={{ backgroundColor: '#e2e8f0', color: '#475569' }}
              >
                返回修改
              </button>
              <button
                onClick={handleConfirmAction}
                className="flex-1 py-3 rounded-xl font-medium transition-all"
                style={{
                  backgroundColor: confirmAction === 'upload' ? '#3b82f6' : '#f97316',
                  color: '#ffffff'
                }}
              >
                確認發布
              </button>
            </div>
          </div>
        </div>
      )}

      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: scale(0.95); }
          to { opacity: 1; transform: scale(1); }
        }
      `}</style>
    </div>
  );
}
