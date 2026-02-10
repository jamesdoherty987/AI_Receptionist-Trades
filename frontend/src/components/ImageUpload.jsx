import { useState, useRef, useEffect } from 'react';
import './ImageUpload.css';

// Compress image to target size (default 300KB to stay under 500KB base64 limit)
const compressImage = (file, maxSizeKB = 300, maxWidth = 800) => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error('Failed to read file'));
    reader.onload = (e) => {
      const img = new Image();
      img.onerror = () => reject(new Error('Failed to load image'));
      img.onload = () => {
        const canvas = document.createElement('canvas');
        let width = img.width;
        let height = img.height;
        
        // Scale down if wider than maxWidth
        if (width > maxWidth) {
          height = (height * maxWidth) / width;
          width = maxWidth;
        }
        
        canvas.width = width;
        canvas.height = height;
        
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, width, height);
        
        // Start with high quality and reduce until under target size
        // Base64 adds ~37% overhead, so target raw size accordingly
        const targetBase64Size = maxSizeKB * 1024;
        let quality = 0.85;
        let result = canvas.toDataURL('image/jpeg', quality);
        
        // Iteratively reduce quality until under target size
        while (result.length > targetBase64Size && quality > 0.1) {
          quality -= 0.1;
          result = canvas.toDataURL('image/jpeg', quality);
        }
        
        // If still too large, reduce dimensions further
        if (result.length > targetBase64Size && width > 400) {
          canvas.width = width * 0.7;
          canvas.height = height * 0.7;
          ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
          result = canvas.toDataURL('image/jpeg', 0.7);
        }
        
        console.log(`Image compressed: ${(result.length / 1024).toFixed(1)}KB at quality ${quality.toFixed(1)}`);
        resolve(result);
      };
      img.src = e.target.result;
    };
    reader.readAsDataURL(file);
  });
};

function ImageUpload({ value, onChange, placeholder = "Upload Image" }) {
  const [preview, setPreview] = useState(value || null);
  const [isDragging, setIsDragging] = useState(false);
  const [isCompressing, setIsCompressing] = useState(false);
  const fileInputRef = useRef(null);

  // Sync preview with value prop changes
  useEffect(() => {
    setPreview(value || null);
  }, [value]);

  const handleFileChange = async (file) => {
    if (!file) return;

    // Validate file type
    if (!file.type.startsWith('image/')) {
      alert('Please select an image file');
      return;
    }

    // Validate file size (max 10MB before compression)
    if (file.size > 10 * 1024 * 1024) {
      alert('Image size must be less than 10MB');
      return;
    }

    setIsCompressing(true);
    
    try {
      // Compress image to ~300KB for database storage compatibility (stays under 500KB base64 limit)
      const compressedBase64 = await compressImage(file, 300, 800);
      setPreview(compressedBase64);
      onChange(compressedBase64);
    } catch (error) {
      console.error('Error compressing image:', error);
      // Fallback to original if compression fails
      const reader = new FileReader();
      reader.onloadend = () => {
        const base64String = reader.result;
        setPreview(base64String);
        onChange(base64String);
      };
      reader.readAsDataURL(file);
    } finally {
      setIsCompressing(false);
    }
  };

  const handleInputChange = (e) => {
    const file = e.target.files[0];
    handleFileChange(file);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    handleFileChange(file);
  };

  const handleRemove = () => {
    setPreview(null);
    onChange('');
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleClick = () => {
    fileInputRef.current?.click();
  };

  return (
    <div className="image-upload-container">
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        onChange={handleInputChange}
        className="image-upload-input"
      />
      
      {preview ? (
        <div className="image-preview">
          <img src={preview} alt="Preview" />
          <div className="image-actions">
            <button 
              type="button" 
              className="btn-change"
              onClick={handleClick}
              disabled={isCompressing}
            >
              <i className="fas fa-camera"></i> Change
            </button>
            <button 
              type="button" 
              className="btn-remove"
              onClick={handleRemove}
              disabled={isCompressing}
            >
              <i className="fas fa-trash"></i>
            </button>
          </div>
        </div>
      ) : (
        <div 
          className={`upload-dropzone ${isDragging ? 'dragging' : ''} ${isCompressing ? 'compressing' : ''}`}
          onClick={handleClick}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          <div className="upload-icon">
            {isCompressing ? (
              <i className="fas fa-spinner fa-spin"></i>
            ) : (
              <i className="fas fa-cloud-upload-alt"></i>
            )}
          </div>
          <p className="upload-text">{isCompressing ? 'Optimizing...' : placeholder}</p>
          <p className="upload-hint">Click or drag & drop</p>
          <p className="upload-hint">Images auto-compressed for best quality</p>
        </div>
      )}
    </div>
  );
}

export default ImageUpload;

