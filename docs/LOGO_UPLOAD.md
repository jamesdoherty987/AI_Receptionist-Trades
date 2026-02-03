# Logo Upload Feature Documentation

## Overview

The logo upload feature allows users to upload their company logo from their device. The system automatically handles storage in either Cloudflare R2 (when configured) or as base64 in the database (fallback).

## How It Works

### Frontend

1. **User uploads image** via drag-and-drop or file picker in Settings
2. **ImageUpload component** validates the image:
   - File type: Must be an image (jpg, png, gif, etc.)
   - File size: Maximum 2MB
3. **Image is converted to base64** and sent to the backend
4. **Preview shown immediately** with options to change or remove

### Backend

1. **Receives base64 image** from frontend
2. **Attempts to upload to R2** (if configured):
   - Extracts image data from base64
   - Generates unique filename: `logo_YYYYMMDD_HHMMSS_random.ext`
   - Uploads to R2 in `/logos` folder
   - Returns public R2 URL
3. **Falls back to base64** storage if:
   - R2 is not configured (missing environment variables)
   - R2 upload fails (network issues, invalid credentials, etc.)
4. **Stores in database**: Either R2 URL or base64 string in `logo_url` column

## R2 Configuration

### Environment Variables

Add these to your `.env` file to enable R2 storage:

```env
# Cloudflare R2 Storage
R2_ACCOUNT_ID=your_cloudflare_account_id
R2_ACCESS_KEY_ID=your_r2_access_key_id
R2_SECRET_ACCESS_KEY=your_r2_secret_access_key
R2_BUCKET_NAME=your_bucket_name
R2_PUBLIC_URL=https://yourbucket.yourdomain.com
```

### Setup Steps

1. **Create R2 Bucket** in Cloudflare Dashboard
2. **Configure CORS** (if needed for direct browser access)
3. **Set bucket to public** or configure custom domain
4. **Generate API tokens** with read/write permissions
5. **Add environment variables** to `.env`
6. **Restart the application**

### Custom Domain Setup

For production, use a custom domain:

1. In Cloudflare Dashboard → R2 → Your Bucket → Settings
2. Enable "Public URL Access" or connect custom domain
3. Set `R2_PUBLIC_URL` to your custom domain (e.g., `https://cdn.yourdomain.com`)

## Database Schema

The logo is stored in the `logo_url` column:

```sql
-- companies table
logo_url TEXT  -- Stores either R2 URL or base64 data

-- business_settings table (for settings manager)
logo_url TEXT  -- Same field for settings-based storage
```

## API Endpoints

### Business Settings Update
```
POST /api/settings/business
Content-Type: application/json

{
  "logo_url": "data:image/png;base64,iVBORw0KGgo..."
}
```

### Profile Update
```
PUT /api/auth/profile
Content-Type: application/json

{
  "logo_url": "data:image/png;base64,iVBORw0KGgo..."
}
```

Both endpoints automatically handle R2 upload and fallback.

## File Structure

```
src/
  ├── app.py                       # API endpoints with R2 logic
  └── services/
      └── storage_r2.py           # R2 storage handler

frontend/
  └── src/
      ├── pages/
      │   └── Settings.jsx        # Uses ImageUpload component
      └── components/
          ├── ImageUpload.jsx     # Reusable image upload component
          ├── ImageUpload.css
          └── Header.jsx          # Displays logo from URL or base64
```

## Supported Image Formats

- JPEG/JPG
- PNG
- GIF
- WebP
- SVG

Maximum file size: **2MB**

## Display Behavior

### In Header
- Logo displayed with `object-fit: contain`
- Maximum dimensions: `36px height`, `120px width`
- Rounded corners for professional appearance

### In Settings Preview
- Preview displayed at `150px height`
- `object-fit: contain` to preserve aspect ratio
- White background for logos with transparency

## Error Handling

### Upload Validation Errors
- **"Please select an image file"**: Non-image file selected
- **"Image size must be less than 2MB"**: File too large

### Backend Errors
- **R2 not configured**: Silently falls back to base64 storage
- **R2 upload failed**: Logs warning, stores base64 instead
- **Invalid image data**: Returns 400 error to frontend

## Testing

### Without R2 (Default)
1. Upload logo in Settings
2. Image stored as base64 in database
3. Logo displays correctly in header
4. Console shows: `"ℹ️ R2 not configured, storing logo as base64"`

### With R2
1. Configure R2 environment variables
2. Restart application
3. Upload logo in Settings
4. Image uploaded to R2
5. R2 URL stored in database
6. Console shows: `"✅ Logo uploaded to R2: https://..."`

## Performance Considerations

### Base64 Storage (Default)
- **Pros**: No external dependencies, works immediately
- **Cons**: Increases database size, slower API responses for large images
- **Recommended for**: Development, small deployments

### R2 Storage (Production)
- **Pros**: Fast CDN delivery, doesn't bloat database, globally distributed
- **Cons**: Requires R2 setup, small cost for storage/bandwidth
- **Recommended for**: Production, high-traffic sites

## Migration from URL to Upload

If you currently have URL-based logos:

1. Users can replace URL with uploaded image in Settings
2. Old URL is overwritten with new image data
3. No migration script needed - happens organically

## Security

- ✅ File type validation prevents malicious uploads
- ✅ File size limit prevents DoS via large files
- ✅ Base64 validation ensures valid image data
- ✅ R2 uses signed URLs (if configured for private buckets)
- ✅ No direct file system access

## Troubleshooting

### Logo not appearing in header
- Check database `logo_url` field has data
- Verify base64 string is complete (starts with `data:image/`)
- For R2 URLs, ensure bucket is public or CORS is configured

### R2 upload failing
- Verify all R2 environment variables are set
- Check R2 API token has write permissions
- Ensure bucket exists and is not full
- Check network connectivity to R2

### Image quality issues
- Ensure original image is high quality
- For logos, use PNG with transparency
- Consider using SVG for scalable logos (future enhancement)

## Future Enhancements

- [ ] Image optimization/compression on upload
- [ ] SVG logo support with sanitization
- [ ] Multiple logo variants (light/dark mode)
- [ ] Logo cropping/editing interface
- [ ] Favicon generation from logo
- [ ] Automatic logo removal from R2 when updating
