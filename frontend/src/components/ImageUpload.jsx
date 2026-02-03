import { useState, useRef, useEffect } from 'react';
import './ImageUpload.css';

function ImageUpload({ value, onChange, placeholder = "Upload Image" }) {
  const [preview, setPreview] = useState(value || null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef(null);

  // Sync preview with value prop changes
  useEffect(() => {
    setPreview(value || null);
  }, [value]);

  const handleFileChange = (file) => {
    if (!file) return;

    // Validate file type
    if (!file.type.startsWith('image/')) {
      alert('Please select an image file');
      return;
    }

    // Validate file size (max 2MB)
    if (file.size > 2 * 1024 * 1024) {
      alert('Image size must be less than 2MB');
      return;
    }

    // Convert to base64
    const reader = new FileReader();
    reader.onloadend = () => {
      const base64String = reader.result;
      setPreview(base64String);
      onChange(base64String);
    };
    reader.readAsDataURL(file);
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
            >
              <i className="fas fa-camera"></i> Change
            </button>
            <button 
              type="button" 
              className="btn-remove"
              onClick={handleRemove}
            >
              <i className="fas fa-trash"></i>
            </button>
          </div>
        </div>
      ) : (
        <div 
          className={`upload-dropzone ${isDragging ? 'dragging' : ''}`}
          onClick={handleClick}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          <div className="upload-icon">
            <i className="fas fa-cloud-upload-alt"></i>
          </div>
          <p className="upload-text">{placeholder}</p>
          <p className="upload-hint">Click or drag & drop</p>
          <p className="upload-hint">Max 2MB • JPG, PNG, GIF</p>
        </div>
      )}
    </div>
  );
}

export default ImageUpload;

