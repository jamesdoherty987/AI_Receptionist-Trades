import { Link } from 'react-router-dom';
import './PrivacyPolicy.css';

function PrivacyPolicy() {
  return (
    <div className="privacy-page">
      <nav className="privacy-nav">
        <div className="nav-container">
          <Link to="/" className="nav-logo">
            <i className="fas fa-bolt"></i>
            <span>BookedForYou</span>
          </Link>
        </div>
      </nav>

      <div className="privacy-container">
        <h1>Privacy Policy</h1>
        <p className="privacy-updated">Last updated: March 25, 2026</p>

        <section className="privacy-section">
          <h2>1. Introduction</h2>
          <p>
            BookedForYou ("we", "our", or "us") operates the BookedForYou platform, 
            including our website and related services (collectively, the "Service"). 
            This Privacy Policy explains how we collect, use, disclose, and safeguard 
            your information when you use our Service.
          </p>
          <p>
            By using the Service, you agree to the collection and use of information 
            in accordance with this policy. If you do not agree with the terms of this 
            Privacy Policy, please do not access or use the Service.
          </p>
        </section>

        <section className="privacy-section">
          <h2>2. Information We Collect</h2>
          <h3>2.1 Information You Provide</h3>
          <ul>
            <li>Account information: name, email address, password, business name</li>
            <li>Business details: services offered, business hours, worker information</li>
            <li>Customer data: names, phone numbers, addresses, and appointment details you enter into the system</li>
            <li>Payment information: processed securely through our payment provider (Stripe). We do not store your full card details.</li>
            <li>Communications: messages you send to us for support or feedback</li>
          </ul>

          <h3>2.2 Information Collected Automatically</h3>
          <ul>
            <li>Log data: IP address and access times for security monitoring</li>
            <li>Session cookies to keep you logged in</li>
          </ul>

          <h3>2.3 Information from Third-Party Services</h3>
          <p>
            When you connect third-party services to your BookedForYou account, we may 
            receive information from those services as described below:
          </p>
          <ul>
            <li>Google Calendar: calendar event data including event titles, times, descriptions, and attendees, used to sync your bookings and prevent scheduling conflicts</li>
            <li>Stripe: subscription status and payment confirmation (we do not receive or store full card numbers)</li>
            <li>Twilio: call metadata and SMS delivery status for AI receptionist functionality</li>
          </ul>
        </section>

        <section className="privacy-section">
          <h2>3. Google User Data</h2>
          <p>
            BookedForYou's use and transfer to any other app of information received from 
            Google APIs will adhere to the{' '}
            <a href="https://developers.google.com/terms/api-services-user-data-policy" target="_blank" rel="noopener noreferrer">
              Google API Services User Data Policy
            </a>, including the Limited Use requirements.
          </p>

          <h3>3.1 What Google Data We Access</h3>
          <p>
            When you choose to connect your Google Calendar, we request access to your 
            Google Calendar data using the following scope:
          </p>
          <ul>
            <li><code>https://www.googleapis.com/auth/calendar</code> — to read and write calendar events</li>
          </ul>

          <h3>3.2 How We Use Google Data</h3>
          <p>We use your Google Calendar data solely to:</p>
          <ul>
            <li>Display your existing calendar events within the BookedForYou scheduling interface</li>
            <li>Create new calendar events when bookings are made through our AI receptionist</li>
            <li>Update or cancel calendar events when bookings are modified or cancelled</li>
            <li>Check availability to prevent double-bookings</li>
          </ul>

          <h3>3.3 How We Store Google Data</h3>
          <p>
            Google Calendar data is cached temporarily in our secure database to provide 
            the scheduling functionality. We store OAuth refresh tokens securely to maintain 
            your calendar connection. Calendar event data is synced in real-time and is not 
            retained beyond what is necessary to provide the Service.
          </p>

          <h3>3.4 How We Share Google Data</h3>
          <p>
            We do not sell, share, or transfer your Google user data to any third parties, 
            except as necessary to provide the Service (e.g., creating calendar events on 
            your behalf). We do not use Google user data for advertising purposes.
          </p>

          <h3>3.5 Revoking Access</h3>
          <p>
            You can disconnect your Google Calendar at any time from your BookedForYou 
            settings page. You can also revoke access directly from your{' '}
            <a href="https://myaccount.google.com/permissions" target="_blank" rel="noopener noreferrer">
              Google Account permissions page
            </a>. Upon revocation, we will delete your stored Google OAuth tokens.
          </p>
        </section>

        <section className="privacy-section">
          <h2>4. How We Use Your Information</h2>
          <p>We use the information we collect to:</p>
          <ul>
            <li>Provide, operate, and maintain the Service</li>
            <li>Process your transactions and manage your subscription</li>
            <li>Handle incoming phone calls via our AI receptionist on your behalf</li>
            <li>Schedule and manage appointments for your business</li>
            <li>Send you SMS reminders and notifications related to bookings</li>
            <li>Send you service-related communications (e.g., account verification, billing)</li>
            <li>Respond to your support requests</li>
            <li>Improve and develop new features for the Service</li>
            <li>Detect, prevent, and address technical issues or abuse</li>
          </ul>
        </section>

        <section className="privacy-section">
          <h2>5. Data Sharing and Disclosure</h2>
          <p>We do not sell your personal information. We may share your information with:</p>
          <ul>
            <li>Service providers: third-party companies that help us operate the Service (e.g., hosting, payment processing, telephony, AI/ML providers). These providers are contractually obligated to protect your data.</li>
            <li>Legal requirements: if required by law, regulation, or legal process</li>
            <li>Business transfers: in connection with a merger, acquisition, or sale of assets, with notice to you</li>
            <li>With your consent: when you explicitly authorize us to share information</li>
          </ul>
        </section>

        <section className="privacy-section">
          <h2>6. Data Security</h2>
          <p>
            We implement appropriate technical and organizational measures to protect your 
            personal information, including encryption in transit (TLS/SSL), secure database 
            storage, and access controls. However, no method of transmission over the Internet 
            is 100% secure, and we cannot guarantee absolute security.
          </p>
        </section>

        <section className="privacy-section">
          <h2>7. Data Retention</h2>
          <p>
            We retain your personal information for as long as your account is active or as 
            needed to provide the Service. If you delete your account, we will delete or 
            anonymize your personal data within 30 days, except where we are required to 
            retain it for legal or regulatory purposes.
          </p>
        </section>

        <section className="privacy-section">
          <h2>8. Your Rights</h2>
          <p>Depending on your location, you may have the following rights:</p>
          <ul>
            <li>Access: request a copy of the personal data we hold about you</li>
            <li>Correction: request correction of inaccurate or incomplete data</li>
            <li>Deletion: request deletion of your personal data</li>
            <li>Portability: request a copy of your data in a portable format</li>
            <li>Objection: object to processing of your data in certain circumstances</li>
            <li>Restriction: request restriction of processing in certain circumstances</li>
            <li>Withdraw consent: where processing is based on consent, you may withdraw it at any time</li>
          </ul>
          <p>
            To exercise any of these rights, please contact us at the email address provided below.
          </p>
        </section>

        <section className="privacy-section">
          <h2>9. Cookies</h2>
          <p>
            We use essential cookies solely to maintain your session and keep you logged in. 
            We do not use analytics or advertising cookies.
          </p>
        </section>

        <section className="privacy-section">
          <h2>10. Children's Privacy</h2>
          <p>
            The Service is not intended for use by anyone under the age of 18. We do not 
            knowingly collect personal information from children. If we become aware that 
            we have collected data from a child, we will take steps to delete it promptly.
          </p>
        </section>

        <section className="privacy-section">
          <h2>11. International Data Transfers</h2>
          <p>
            Your information may be transferred to and processed in countries other than 
            your own. We ensure appropriate safeguards are in place to protect your data 
            in accordance with applicable data protection laws.
          </p>
        </section>

        <section className="privacy-section">
          <h2>12. Changes to This Policy</h2>
          <p>
            We may update this Privacy Policy from time to time. We will notify you of 
            any material changes by posting the new policy on this page and updating the 
            "Last updated" date. Your continued use of the Service after changes are posted 
            constitutes your acceptance of the updated policy.
          </p>
        </section>

        <section className="privacy-section">
          <h2>13. Contact Us</h2>
          <p>
            If you have any questions about this Privacy Policy or our data practices, 
            please contact us at:
          </p>
          <p className="contact-info">
            Email: <a href="mailto:j.p.enterprisehq@gmail.com">j.p.enterprisehq@gmail.com</a>
          </p>
        </section>
      </div>

      <footer className="privacy-footer">
        <p>&copy; 2026 BookedForYou. All rights reserved.</p>
        <Link to="/">Back to Home</Link>
      </footer>
    </div>
  );
}

export default PrivacyPolicy;
