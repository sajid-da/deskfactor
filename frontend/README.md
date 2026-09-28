# ClearNote Frontend

React + TypeScript + Vite interface with a responsive dashboard, page transitions and result animations using Framer Motion.

## Development

```powershell
npm ci
npm run dev
```

The development server is at `http://localhost:5173`. It calls `http://localhost:8000` by default. Set `VITE_API_URL` at build time to change the backend base URL. The Documents view supports text, PDF, and image uploads; image OCR offers automatic, printed, or handwritten mode. The production container serves the app through Nginx and proxies `/api` to FastAPI.

Use synthetic clinical information only. The UI is a documentation-review aid, not a diagnosis or treatment tool.
