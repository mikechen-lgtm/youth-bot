import { useState } from "react";
import { HeroImage } from "../../services/adminApi";
import { ImageCard } from "./ImageCard";

interface ImageListProps {
  images: HeroImage[];
  onDelete: (id: number) => Promise<void>;
  onUpdateAlt: (id: number, altText: string) => Promise<void>;
  onReorder: (newOrder: number[]) => Promise<void>;
}

export function ImageList({
  images,
  onDelete,
  onUpdateAlt,
  onReorder,
}: ImageListProps) {
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);

  const handleDragStart = (index: number) => {
    setDraggedIndex(index);
  };

  const handleDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault();
    if (draggedIndex === null || draggedIndex === index) return;
    setDragOverIndex(index);
  };

  const handleDragEnd = async () => {
    if (draggedIndex === null || dragOverIndex === null || draggedIndex === dragOverIndex) {
      setDraggedIndex(null);
      setDragOverIndex(null);
      return;
    }

    // Reorder the array
    const newImages = [...images];
    const [removed] = newImages.splice(draggedIndex, 1);
    newImages.splice(dragOverIndex, 0, removed);

    // Get new order of IDs
    const newOrder = newImages.map((img) => img.id);

    setDraggedIndex(null);
    setDragOverIndex(null);

    // Call API to save new order
    await onReorder(newOrder);
  };

  if (images.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
        目前沒有圖片，請上傳第一張 Hero Banner
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-lg font-semibold mb-4">
        圖片列表 ({images.length} 張)
      </h2>
      <p className="text-sm text-gray-500 mb-4">
        拖曳圖片可以調整顯示順序
      </p>

      <div className="space-y-3">
        {images.map((image, index) => (
          <div
            key={image.id}
            draggable
            onDragStart={() => handleDragStart(index)}
            onDragOver={(e) => handleDragOver(e, index)}
            onDragEnd={handleDragEnd}
            className={`
              transition-all duration-200
              ${dragOverIndex === index ? "transform translate-y-2" : ""}
            `}
          >
            <ImageCard
              image={image}
              onDelete={onDelete}
              onUpdateAlt={onUpdateAlt}
              isDragging={draggedIndex === index}
              dragHandleProps={{
                onMouseDown: (e) => e.stopPropagation(),
              }}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
