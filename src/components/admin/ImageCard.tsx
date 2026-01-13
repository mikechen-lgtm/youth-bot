import { useState } from "react";
import { Trash2, GripVertical, Edit2, Check, X } from "lucide-react";
import { HeroImage } from "../../services/adminApi";

interface ImageCardProps {
  image: HeroImage;
  onDelete: (id: number) => Promise<void>;
  onUpdateAlt: (id: number, altText: string) => Promise<void>;
  isDragging?: boolean;
  dragHandleProps?: React.HTMLAttributes<HTMLDivElement>;
}

export function ImageCard({
  image,
  onDelete,
  onUpdateAlt,
  isDragging,
  dragHandleProps,
}: ImageCardProps) {
  const [isDeleting, setIsDeleting] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editAltText, setEditAltText] = useState(image.alt_text || "");
  const [isSaving, setIsSaving] = useState(false);

  const handleDelete = async () => {
    if (!confirm("確定要刪除這張圖片嗎？")) return;

    setIsDeleting(true);
    try {
      await onDelete(image.id);
    } finally {
      setIsDeleting(false);
    }
  };

  const handleSaveAlt = async () => {
    setIsSaving(true);
    try {
      await onUpdateAlt(image.id, editAltText);
      setIsEditing(false);
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancelEdit = () => {
    setEditAltText(image.alt_text || "");
    setIsEditing(false);
  };

  return (
    <div
      className={`
        bg-white rounded-lg shadow overflow-hidden transition-shadow
        ${isDragging ? "shadow-lg ring-2 ring-blue-500" : ""}
      `}
    >
      <div className="flex">
        {/* Drag handle */}
        <div
          {...dragHandleProps}
          className="flex items-center justify-center w-10 bg-gray-100 cursor-grab active:cursor-grabbing hover:bg-gray-200"
        >
          <GripVertical className="text-gray-400" size={20} />
        </div>

        {/* Image preview */}
        <div className="w-40 h-24 flex-shrink-0">
          <img
            src={image.url}
            alt={image.alt_text || "Hero image"}
            className="w-full h-full object-cover"
          />
        </div>

        {/* Info */}
        <div className="flex-1 p-3 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1 min-w-0">
              <p className="text-sm text-gray-500 mb-1">
                順序: {image.display_order + 1}
              </p>

              {isEditing ? (
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={editAltText}
                    onChange={(e) => setEditAltText(e.target.value)}
                    placeholder="輸入圖片描述"
                    className="flex-1 px-2 py-1 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-500"
                    disabled={isSaving}
                  />
                  <button
                    onClick={handleSaveAlt}
                    disabled={isSaving}
                    className="p-1 text-green-600 hover:bg-green-50 rounded"
                  >
                    <Check size={18} />
                  </button>
                  <button
                    onClick={handleCancelEdit}
                    disabled={isSaving}
                    className="p-1 text-gray-500 hover:bg-gray-100 rounded"
                  >
                    <X size={18} />
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <p className="text-sm text-gray-700 truncate">
                    {image.alt_text || "(無描述)"}
                  </p>
                  <button
                    onClick={() => setIsEditing(true)}
                    className="p-1 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded"
                  >
                    <Edit2 size={14} />
                  </button>
                </div>
              )}
            </div>

            {/* Delete button */}
            <button
              onClick={handleDelete}
              disabled={isDeleting}
              className="p-2 text-red-500 hover:bg-red-50 rounded-md disabled:opacity-50"
              title="刪除"
            >
              <Trash2 size={18} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
