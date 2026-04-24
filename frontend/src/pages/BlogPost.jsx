import { Link, useParams, Navigate } from 'react-router-dom';
import { useEffect } from 'react';
import blogPosts from '../data/blogPosts';
import blogContentMap from '../data/blogContent';
import './Blog.css';

function BlogPost() {
  const { slug } = useParams();
  const post = blogPosts.find(p => p.slug === slug);
  const ContentComponent = blogContentMap[slug];

  useEffect(() => { window.scrollTo(0, 0); }, [slug]);

  if (!post || !ContentComponent) {
    return <Navigate to="/blog" replace />;
  }

  const relatedPosts = blogPosts
    .filter(p => p.slug !== slug && blogContentMap[p.slug])
    .slice(0, 3);

  return (
    <div className="blog-page">
      <nav className="blog-nav">
        <div className="nav-container">
          <Link to="/" className="nav-logo">
            <i className="fas fa-bolt"></i>
            <span>BookedForYou</span>
          </Link>
          <div className="nav-right">
            <Link to="/blog" className="nav-link-btn">All Articles</Link>
            <a href="mailto:contact@bookedforyou.ie?subject=Get Started with BookedForYou" className="nav-btn-primary">Get Started</a>
          </div>
        </div>
      </nav>

      <article className="blog-article-container">
        <div className="blog-article-header">
          <Link to="/blog" className="blog-back-link">
            <i className="fas fa-arrow-left"></i> Back to Blog
          </Link>
          <span className="blog-article-category">{post.category}</span>
          <h1>{post.title}</h1>
          <div className="blog-article-meta">
            <span><i className="far fa-calendar"></i> {formatDate(post.date)}</span>
            <span><i className="far fa-clock"></i> {post.readTime}</span>
          </div>
        </div>

        <div className="blog-article-body">
          <ContentComponent />
        </div>
      </article>

      {relatedPosts.length > 0 && (
        <div className="blog-related">
          <div className="blog-related-inner">
            <h2>More Articles</h2>
            <div className="blog-related-grid">
              {relatedPosts.map(rp => (
                <Link to={`/blog/${rp.slug}`} key={rp.slug} className="blog-related-card">
                  <span className="blog-related-category">{rp.category}</span>
                  <h3>{rp.title}</h3>
                  <span className="blog-related-meta">{rp.readTime}</span>
                </Link>
              ))}
            </div>
          </div>
        </div>
      )}

      <footer className="blog-footer">
        <div className="blog-footer-inner">
          <p>&copy; 2026 BookedForYou. All rights reserved.</p>
          <div className="blog-footer-links">
            <Link to="/">Home</Link>
            <Link to="/blog">Blog</Link>
            <Link to="/privacy">Privacy</Link>
            <Link to="/terms">Terms</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}

function formatDate(dateStr) {
  const d = new Date(dateStr + 'T00:00:00');
  return d.toLocaleDateString('en-IE', { day: 'numeric', month: 'long', year: 'numeric' });
}

export default BlogPost;
