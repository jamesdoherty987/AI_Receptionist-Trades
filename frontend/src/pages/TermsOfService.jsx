import { Link } from 'react-router-dom';
import './PrivacyPolicy.css';

function TermsOfService() {
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
        <h1>Terms of Service</h1>
        <p className="privacy-updated">Last updated: March 25, 2026</p>

        <section className="privacy-section">
          <h2>1. Acceptance of Terms</h2>
          <p>
            By accessing or using the BookedForYou platform ("Service"), operated by
            BookedForYou ("we", "our", or "us"), you agree to be bound by these Terms
            of Service. If you do not agree to these terms, you may not use the Service.
          </p>
        </section>

        <section className="privacy-section">
          <h2>2. Description of Service</h2>
          <p>
            BookedForYou provides an AI-powered receptionist and business management
            platform designed for trade businesses. The Service includes:
          </p>
          <ul>
            <li>AI phone receptionist that answers calls on your behalf</li>
            <li>Appointment booking and scheduling</li>
            <li>Customer and employee management</li>
            <li>Google Calendar integration</li>
            <li>Invoicing and financial tracking</li>
            <li>SMS and email notifications</li>
          </ul>
        </section>

        <section className="privacy-section">
          <h2>3. Account Registration</h2>
          <p>
            To use the Service, you must create an account and provide accurate, complete
            information. You are responsible for maintaining the confidentiality of your
            account credentials and for all activities that occur under your account.
          </p>
          <p>
            You must be at least 18 years old to create an account. By registering, you
            represent that you have the legal authority to enter into these terms on behalf
            of yourself or your business.
          </p>
        </section>

        <section className="privacy-section">
          <h2>4. Free Trial and Subscription</h2>
          <p>
            We offer a 14-day free trial that includes access to all features. After the
            trial period, continued use of the Service requires an active paid subscription.
          </p>
          <p>
            Subscription fees are billed monthly through our payment provider, Stripe.
            You may cancel your subscription at any time. Cancellation takes effect at the
            end of the current billing period, and no refunds are provided for partial months.
          </p>
          <p>
            We reserve the right to change subscription pricing with 30 days' notice. Continued
            use of the Service after a price change constitutes acceptance of the new pricing.
          </p>
        </section>

        <section className="privacy-section">
          <h2>5. Acceptable Use</h2>
          <p>You agree not to:</p>
          <ul>
            <li>Use the Service for any unlawful purpose or in violation of any applicable laws</li>
            <li>Attempt to gain unauthorised access to the Service or its related systems</li>
            <li>Interfere with or disrupt the integrity or performance of the Service</li>
            <li>Use the Service to transmit spam, harassment, or abusive content</li>
            <li>Reverse engineer, decompile, or disassemble any part of the Service</li>
            <li>Resell, sublicense, or redistribute the Service without our written consent</li>
            <li>Use the AI receptionist for fraudulent or deceptive purposes</li>
          </ul>
        </section>

        <section className="privacy-section">
          <h2>6. Your Data and Content</h2>
          <p>
            You retain ownership of all data and content you upload or input into the Service,
            including customer information, business details, and job records. You grant us a
            limited licence to use this data solely to provide and improve the Service.
          </p>
          <p>
            You are responsible for ensuring that you have the necessary rights and consents
            to input any personal data into the Service, including customer phone numbers,
            email addresses, and other personal information.
          </p>
        </section>

        <section className="privacy-section">
          <h2>7. AI Receptionist</h2>
          <p>
            The AI receptionist is an automated system that handles phone calls on your behalf.
            While we strive for accuracy, the AI may occasionally misinterpret caller requests
            or make errors in booking details. You acknowledge that:
          </p>
          <ul>
            <li>The AI receptionist is not a substitute for human judgement in critical situations</li>
            <li>You are responsible for reviewing and confirming bookings made by the AI</li>
            <li>We are not liable for any losses arising from AI errors or misinterpretations</li>
            <li>Call recordings and transcriptions may be processed to provide the Service</li>
          </ul>
        </section>

        <section className="privacy-section">
          <h2>8. Third-Party Integrations</h2>
          <p>
            The Service integrates with third-party services including Google Calendar, Telnyx,
            Stripe, and Deepgram. Your use of these integrations is subject to the respective
            third-party terms of service. We are not responsible for the availability or
            performance of third-party services.
          </p>
          <p>
            When you connect your Google Calendar, our use of Google data is governed by our{' '}
            <Link to="/privacy">Privacy Policy</Link> and the{' '}
            <a href="https://developers.google.com/terms/api-services-user-data-policy" target="_blank" rel="noopener noreferrer">
              Google API Services User Data Policy
            </a>.
          </p>
        </section>

        <section className="privacy-section">
          <h2>9. Intellectual Property</h2>
          <p>
            The Service, including its design, code, features, and branding, is owned by
            BookedForYou and is protected by intellectual property laws. Nothing in these
            terms grants you any right to use our trademarks, logos, or branding without
            our prior written consent.
          </p>
        </section>

        <section className="privacy-section">
          <h2>10. Limitation of Liability</h2>
          <p>
            To the maximum extent permitted by law, BookedForYou shall not be liable for
            any indirect, incidental, special, consequential, or punitive damages, including
            but not limited to loss of profits, data, business opportunities, or goodwill,
            arising out of or in connection with your use of the Service.
          </p>
          <p>
            Our total liability for any claim arising from the Service shall not exceed the
            amount you paid us in the 12 months preceding the claim.
          </p>
        </section>

        <section className="privacy-section">
          <h2>11. Disclaimer of Warranties</h2>
          <p>
            The Service is provided "as is" and "as available" without warranties of any kind,
            whether express or implied, including but not limited to implied warranties of
            merchantability, fitness for a particular purpose, and non-infringement.
          </p>
          <p>
            We do not warrant that the Service will be uninterrupted, error-free, or secure,
            or that any defects will be corrected.
          </p>
        </section>

        <section className="privacy-section">
          <h2>12. Termination</h2>
          <p>
            We may suspend or terminate your access to the Service at any time if you violate
            these terms or engage in conduct that we determine is harmful to the Service or
            other users. You may terminate your account at any time by contacting us.
          </p>
          <p>
            Upon termination, your right to use the Service ceases immediately. We will
            delete your data in accordance with our <Link to="/privacy">Privacy Policy</Link>.
          </p>
        </section>

        <section className="privacy-section">
          <h2>13. Changes to These Terms</h2>
          <p>
            We may update these Terms of Service from time to time. We will notify you of
            material changes by posting the updated terms on this page and updating the
            "Last updated" date. Your continued use of the Service after changes are posted
            constitutes acceptance of the revised terms.
          </p>
        </section>

        <section className="privacy-section">
          <h2>14. Governing Law</h2>
          <p>
            These terms shall be governed by and construed in accordance with the laws of
            Ireland, without regard to its conflict of law provisions. Any disputes arising
            from these terms or the Service shall be subject to the exclusive jurisdiction
            of the courts of Ireland.
          </p>
        </section>

        <section className="privacy-section">
          <h2>15. Contact Us</h2>
          <p>
            If you have any questions about these Terms of Service, please contact us at:
          </p>
          <p className="contact-info">
            Email: <a href="mailto:contact@bookedforyou.ie">contact@bookedforyou.ie</a>
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

export default TermsOfService;
