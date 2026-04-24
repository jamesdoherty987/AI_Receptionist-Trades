import { Link } from 'react-router-dom';
import { useEffect } from 'react';
import blogPosts from '../data/blogPosts';
import blogContentMap from '../data/blogContent';
import './Blog.css';

// Only show posts that have actual content
const publishedPosts = blogPosts.filter(p => blogContentMap[p.slug]);

const categoryColors = {
  'Business Growth': '#ef4444',
  'Cost Savings': '#10b981',
  'Tips & Tricks': '#0ea5e9',
  'Productivity': '#f97316',
  'Technology': '#8b5cf6',
  'Customer Experience': '#ec4899',
};

function Blog() {
  useEffect(() => { window.scrollTo(0, 0); }, []);

  return (
    <div className="blog-page">
      <nav className="blog-nav">
        <div className="nav-container">
          <Link to="/" className="nav-logo">
            <i className="fas fa-bolt"></i>
            <span>BookedForYou</span>
          </Link>
          <div className="nav-right">
            <Link to="/login" className="nav-link-btn">Log In</Link>
            <Link to="/#pricing" className="nav-btn-primary">Get Started</Link>
          </div>
        </div>
      </nav>

      <div className="blog-hero">
        <h1>The BookedForYou Blog</h1>
        <p>Tips, insights, and guides for tradespeople who want to grow their business.</p>
      </div>

      <div className="blog-list-container">
        <div className="blog-grid">
          {publishedPosts.map((post) => (
            <Link to={`/blog/${post.slug}`} key={post.slug} className="blog-card">
              <div className="blog-card-icon">
                <i className={getCategoryIcon(post.category)}></i>
              </div>
              <div className="blog-card-category" style={{ color: categoryColors[post.category] || '#0ea5e9' }}>
                {post.category}
              </div>
              <h2 className="blog-card-title">{post.title}</h2>
              <p className="blog-card-desc">{post.description}</p>
              <div className="blog-card-meta">
                <span><i className="far fa-calendar"></i> {formatDate(post.date)}</span>
                <span><i className="far fa-clock"></i> {post.readTime}</span>
              </div>
            </Link>
          ))}
        </div>
      </div>

      <footer className="blog-footer">
        <div className="blog-footer-inner">
          <p>&copy; 2026 BookedForYou. All rights reserved.</p>
          <div className="blog-footer-links">
            <Link to="/">Home</Link>
            <Link to="/privacy">Privacy</Link>
            <Link to="/terms">Terms</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}

function getCategoryIcon(category) {
  const icons = {
    'Business Growth': 'fas fa-chart-line',
    'Cost Savings': 'fas fa-piggy-bank',
    'Tips & Tricks': 'fas fa-wrench',
    'Productivity': 'fas fa-calendar-check',
    'Technology': 'fas fa-sync-alt',
    'Customer Experience': 'fas fa-star',
  };
  return icons[category] || 'fas fa-newspaper';
}

function formatDate(dateStr) {
  const d = new Date(dateStr + 'T00:00:00');
  return d.toLocaleDateString('en-IE', { day: 'numeric', month: 'long', year: 'numeric' });
}

export default Blog;
