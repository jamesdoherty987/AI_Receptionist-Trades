# AI Receptionist Frontend

Modern React application for managing your AI receptionist and business operations.

## Tech Stack

- **React 18** - UI library
- **Vite** - Build tool and dev server
- **React Router** - Client-side routing
- **React Query (TanStack Query)** - Server state management
- **Axios** - HTTP client
- **date-fns** - Date utilities
- **Recharts** - Charts (if needed in future)

## Getting Started

### Prerequisites

- Node.js 16+ and npm
- Python backend running on `http://localhost:5000`

### Installation

```bash
npm install
```

### Development

Start the development server:

```bash
npm run dev
```

The app will be available at `http://localhost:3000`

### Building for Production

```bash
npm run build
```

This creates optimized files in `../src/static/dist/` which the Flask backend serves.

### Preview Production Build

```bash
npm run preview
```

## Project Structure

```
src/
├── components/          # Reusable components
│   ├── Header.jsx      # App header with navigation
│   ├── Tabs.jsx        # Tab component
│   ├── LoadingSpinner.jsx
│   └── dashboard/      # Dashboard-specific components
│       ├── JobsTab.jsx
│       ├── CustomersTab.jsx
│       ├── WorkersTab.jsx
│       ├── FinancesTab.jsx
│       ├── CalendarTab.jsx
│       └── ChatTab.jsx
├── pages/              # Page components (routes)
│   ├── Dashboard.jsx   # Main dashboard
│   ├── Settings.jsx    # Business settings
│   ├── SettingsMenu.jsx
│   └── SettingsDeveloper.jsx
├── services/
│   └── api.js         # API client and endpoints
├── utils/
│   └── helpers.js     # Utility functions
├── App.jsx            # Root component with routing
├── main.jsx           # Entry point
└── index.css          # Global styles
```

## Key Features

### Smart Data Fetching
Uses React Query for:
- Automatic caching
- Background refetching
- Optimistic updates
- Loading and error states

### Responsive Design
- Mobile-first approach
- Works on all screen sizes
- Touch-friendly interfaces

### Modern UI
- Glassmorphism design
- Smooth animations
- Professional color scheme
- Accessible components

## API Integration

All API calls go through `src/services/api.js`:

```javascript
import { getBookings, updateBooking } from './services/api';

// In your component
const { data, isLoading } = useQuery({
  queryKey: ['bookings'],
  queryFn: async () => {
    const response = await getBookings();
    return response.data;
  }
});
```

## Environment Variables

Create a `.env` file if needed:

```env
VITE_API_URL=http://localhost:5000
```

Access in code:
```javascript
const apiUrl = import.meta.env.VITE_API_URL;
```

## Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run preview` - Preview production build
- `npm run lint` - Run ESLint

## Adding New Features

### Add a new page
1. Create component in `src/pages/`
2. Add route in `src/App.jsx`
3. Add navigation link in `src/components/Header.jsx`

### Add a new API endpoint
1. Add function in `src/services/api.js`
2. Use with React Query in your component

### Add a new component
1. Create `.jsx` and `.css` files in `src/components/`
2. Import and use in your pages

## Best Practices

- Use functional components with hooks
- Keep components small and focused
- Use React Query for all server data
- Follow the existing file structure
- Add PropTypes or TypeScript for type safety
- Write semantic HTML
- Use CSS modules or scoped styles

## Troubleshooting

### CORS errors
Make sure the Flask backend has `flask-cors` installed and configured.

### API not responding
Check that the backend is running on port 5000.

### Build errors
Clear node_modules and reinstall:
```bash
rm -rf node_modules
npm install
```

## License

Same as parent project
