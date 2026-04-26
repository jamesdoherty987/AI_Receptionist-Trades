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
        <p className="privacy-updated">Last updated: April 26, 2026</p>

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
            <li>Business details: services offered, business hours, employee information</li>
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
            <li>Telnyx: call metadata and SMS delivery status for AI receptionist functionality</li>
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
          <p>
            We use your Google Calendar data exclusively to provide the calendar 
            synchronization feature within BookedForYou. Specifically, we use it to:
          </p>
          <ul>
            <li>Display your existing calendar events within the BookedForYou scheduling interface</li>
            <li>Create new calendar events when bookings are made through our AI receptionist</li>
            <li>Update or cancel calendar events when bookings are modified or cancelled</li>
            <li>Check availability to prevent double-bookings</li>
          </ul>
          <p>
            Google user data is not used for any other purpose.
          </p>

          <h3>3.3 How We Store Google Data</h3>
          <p>
            We store your Google OAuth refresh token in our encrypted database solely to 
            maintain your calendar connection. Calendar event data (titles, times, descriptions) 
            is stored in our database only as needed to display your schedule and prevent 
            booking conflicts. No Google user data is stored beyond what is required to 
            provide the calendar synchronization feature.
          </p>

          <h3>3.4 How We Share Google Data</h3>
          <p>
            We do not share, sell, or transfer your Google user data to any third parties 
            for any reason. Google user data is only transmitted back to Google via the 
            Google Calendar API to create, update, or delete calendar events on your behalf. 
            No human at BookedForYou accesses your Google user data except for responding 
            to your direct support requests, with your permission.
          </p>

          <h3>3.5 Prohibited Uses of Google Data</h3>
          <p>
            BookedForYou does not use Google user data for any purpose other than providing 
            the user-facing calendar synchronization feature described above. We do not use 
            Google user data for:
          </p>
          <ul>
            <li>Advertising of any kind, including targeted, personalized, retargeted, or interest-based advertising</li>
            <li>Selling or providing data to third parties, data brokers, or information resellers</li>
            <li>Determining credit-worthiness or for lending purposes</li>
            <li>Training artificial intelligence or machine learning models of any kind</li>
            <li>Building or augmenting user profiles, contact databases, or any dataset unrelated to the calendar synchronization feature</li>
            <li>Any purpose other than providing the calendar synchronization feature to you</li>
          </ul>

          <h3>3.6 Revoking Access</h3>
          <p>
            You can disconnect your Google Calendar at any time from your BookedForYou 
            settings page. You can also revoke access directly from your{' '}
            <a href="https://myaccount.google.com/permissions" target="_blank" rel="noopener noreferrer">
              Google Account permissions page
            </a>. When you disconnect or revoke access, we immediately delete your stored 
            Google OAuth tokens and cease all access to your Google Calendar data.
          </p>
        </section>

        <section className="privacy-section">
          <h2>4. How We Use Your Information</h2>
          <p>
            We use the information we collect (other than Google user data, which is 
            governed exclusively by Section 3 above) to:
          </p>
          <ul>
            <li>Provide, operate, and maintain the Service</li>
            <li>Process your transactions and manage your subscription</li>
            <li>Handle incoming phone calls via our AI receptionist on your behalf</li>
            <li>Schedule and manage appointments for your business</li>
            <li>Send you SMS reminders and notifications related to bookings</li>
            <li>Send you service-related communications (e.g., account verification, billing)</li>
            <li>Respond to your support requests</li>
            <li>Detect, prevent, and address technical issues or abuse</li>
          </ul>
        </section>

        <section className="privacy-section">
          <h2>5. Lawful Basis for Processing (GDPR Article 6)</h2>
          <p>
            Under the General Data Protection Regulation (GDPR), we are required to have a 
            valid lawful basis for each type of personal data processing we carry out. The 
            table below sets out the lawful basis we rely on for each processing activity:
          </p>

          <h3>5.1 Contract Performance (Article 6(1)(b))</h3>
          <p>
            We process personal data where it is necessary to perform our contract with you 
            or to take steps at your request before entering into a contract. This includes:
          </p>
          <ul>
            <li>Creating and managing your BookedForYou account</li>
            <li>Providing the AI receptionist service, including answering calls, scheduling appointments, and managing bookings on your behalf</li>
            <li>Processing subscription payments through Stripe</li>
            <li>Syncing your calendar data when you connect Google Calendar</li>
            <li>Sending booking confirmations, reminders, and appointment-related SMS notifications</li>
            <li>Providing customer and employee management features</li>
            <li>Generating invoices, quotes, and financial records</li>
          </ul>

          <h3>5.2 Legitimate Interests (Article 6(1)(f))</h3>
          <p>
            We process personal data where it is necessary for our legitimate interests or 
            those of a third party, provided those interests are not overridden by your 
            rights and freedoms. Our legitimate interests include:
          </p>
          <ul>
            <li>Creating leads from phone enquiries to help you follow up with potential customers (the caller's phone number and any details they voluntarily provide during the call are recorded for this purpose)</li>
            <li>Generating call summaries and transcriptions to improve the quality of service provided to your business</li>
            <li>Maintaining call logs for your business records and quality assurance</li>
            <li>Detecting, preventing, and addressing fraud, abuse, security risks, and technical issues</li>
            <li>Improving and optimising the Service based on usage patterns</li>
          </ul>

          <h3>5.3 Legal Obligation (Article 6(1)(c))</h3>
          <p>
            We process personal data where it is necessary to comply with a legal obligation, 
            including:
          </p>
          <ul>
            <li>Retaining financial and transaction records as required by Irish tax and accounting law</li>
            <li>Responding to lawful requests from regulatory authorities or law enforcement</li>
          </ul>

          <h3>5.4 Consent (Article 6(1)(a))</h3>
          <p>
            Where none of the above bases apply, we will seek your explicit consent before 
            processing your personal data. You have the right to withdraw consent at any 
            time without affecting the lawfulness of processing carried out before withdrawal. 
            Consent is relied upon for:
          </p>
          <ul>
            <li>Connecting optional third-party integrations (e.g., Google Calendar, Xero, QuickBooks)</li>
            <li>Sending marketing or promotional communications (if applicable in the future)</li>
          </ul>
        </section>

        <section className="privacy-section">
          <h2>6. Data Sharing and Disclosure</h2>
          <p>We do not sell your personal information. We may share information (excluding Google user data) with:</p>
          <ul>
            <li>Service providers: third-party companies that help us operate the Service (e.g., hosting, payment processing, telephony). These providers are bound by Data Processing Agreements (see Section 7 below).</li>
            <li>Legal requirements: if required by law, regulation, or legal process</li>
            <li>Business transfers: in connection with a merger, acquisition, or sale of assets, with notice to you</li>
            <li>With your consent: when you explicitly authorize us to share information</li>
          </ul>
          <p>
            Google user data is never shared with any third party for any reason. It is 
            only transmitted back to Google via the Google Calendar API to provide the 
            calendar synchronization feature. See Section 3 for full details.
          </p>
        </section>

        <section className="privacy-section">
          <h2>7. Data Processors and Sub-Processors (GDPR Article 28)</h2>
          <p>
            In order to provide the Service, we engage third-party service providers 
            ("data processors") who process personal data on our behalf. In accordance 
            with Article 28 of the GDPR, we have entered into Data Processing Agreements 
            (DPAs) with each of these processors. These agreements ensure that processors:
          </p>
          <ul>
            <li>Process personal data only on our documented instructions</li>
            <li>Ensure that persons authorised to process the data are bound by confidentiality obligations</li>
            <li>Implement appropriate technical and organisational security measures</li>
            <li>Assist us in responding to data subject rights requests</li>
            <li>Delete or return all personal data at the end of the service relationship</li>
            <li>Make available all information necessary to demonstrate compliance and allow for audits</li>
          </ul>

          <h3>7.1 Our Data Processors</h3>
          <p>The following third-party processors handle personal data as part of the Service:</p>
          <ul>
            <li>
              <strong>Stripe</strong> (Stripe Payments Europe, Ltd.) — processes subscription 
              payments and billing information. Stripe is certified under the EU-U.S. Data 
              Privacy Framework. <a href="https://stripe.com/ie/privacy" target="_blank" rel="noopener noreferrer">Stripe Privacy Policy</a>
            </li>
            <li>
              <strong>Telnyx</strong> (Telnyx LLC) — provides telephony infrastructure for 
              the AI receptionist, including call routing, call metadata, and SMS delivery. 
              <a href="https://telnyx.com/privacy-policy" target="_blank" rel="noopener noreferrer">Telnyx Privacy Policy</a>
            </li>
            <li>
              <strong>Deepgram</strong> (Deepgram, Inc.) — provides speech-to-text 
              (transcription) and text-to-speech services for the AI receptionist. Audio 
              data is processed in real time and is not retained by Deepgram after processing. 
              <a href="https://deepgram.com/privacy" target="_blank" rel="noopener noreferrer">Deepgram Privacy Policy</a>
            </li>
            <li>
              <strong>OpenAI</strong> (OpenAI, LLC) — provides AI language model services 
              used to generate call summaries and power the AI receptionist's conversational 
              abilities. Call transcript data sent to OpenAI is not used to train their 
              models when accessed via the API. 
              <a href="https://openai.com/policies/privacy-policy" target="_blank" rel="noopener noreferrer">OpenAI Privacy Policy</a>
            </li>
            <li>
              <strong>Google</strong> (Google Ireland Limited) — provides calendar 
              synchronisation when you choose to connect Google Calendar. Google user data 
              is governed exclusively by Section 3 of this policy. 
              <a href="https://policies.google.com/privacy" target="_blank" rel="noopener noreferrer">Google Privacy Policy</a>
            </li>
          </ul>

          <h3>7.2 Sub-Processor Changes</h3>
          <p>
            We will notify you of any intended changes to our data processors by updating 
            this Privacy Policy. Where a new processor is engaged, we ensure that a DPA 
            meeting the requirements of Article 28 GDPR is in place before any personal 
            data is shared.
          </p>
        </section>

        <section className="privacy-section">
          <h2>8. Data Security</h2>
          <p>
            We implement appropriate technical and organizational measures to protect your 
            personal information, including encryption in transit (TLS/SSL), secure database 
            storage, and access controls. However, no method of transmission over the Internet 
            is 100% secure, and we cannot guarantee absolute security.
          </p>
        </section>

        <section className="privacy-section">
          <h2>9. Data Retention</h2>
          <p>
            We retain your personal information for as long as your account is active or as 
            needed to provide the Service. If you delete your account, we will delete or 
            anonymize your personal data within 30 days, except where we are required to 
            retain it for legal or regulatory purposes.
          </p>
        </section>

        <section className="privacy-section">
          <h2>10. Your Rights Under GDPR</h2>
          <p>
            Under the GDPR, you have the following rights in relation to your personal data:
          </p>
          <ul>
            <li><strong>Right of Access</strong> (Article 15): request a copy of the personal data we hold about you</li>
            <li><strong>Right to Rectification</strong> (Article 16): request correction of inaccurate or incomplete data</li>
            <li><strong>Right to Erasure</strong> (Article 17): request deletion of your personal data where there is no compelling reason for continued processing</li>
            <li><strong>Right to Data Portability</strong> (Article 20): request a copy of your data in a structured, commonly used, machine-readable format. You can do this directly from your Settings page using the "Download My Data" feature.</li>
            <li><strong>Right to Object</strong> (Article 21): object to processing based on legitimate interests, including profiling</li>
            <li><strong>Right to Restrict Processing</strong> (Article 18): request restriction of processing in certain circumstances</li>
            <li><strong>Right to Withdraw Consent</strong>: where processing is based on consent, you may withdraw it at any time without affecting the lawfulness of processing carried out before withdrawal</li>
          </ul>
          <p>
            To exercise any of these rights, please contact us at the email address provided 
            below. We will respond to your request within one month, as required by the GDPR.
          </p>
          <p>
            You also have the right to lodge a complaint with the Irish Data Protection 
            Commission (DPC) if you believe your data protection rights have been violated:
          </p>
          <p className="contact-info">
            Data Protection Commission<br />
            21 Fitzwilliam Square South, Dublin 2, D02 RD28, Ireland<br />
            Website: <a href="https://www.dataprotection.ie" target="_blank" rel="noopener noreferrer">www.dataprotection.ie</a>
          </p>
        </section>

        <section className="privacy-section">
          <h2>11. Cookies</h2>
          <p>
            We use essential cookies solely to maintain your session and keep you logged in. 
            We do not use analytics or advertising cookies.
          </p>
        </section>

        <section className="privacy-section">
          <h2>12. Children's Privacy</h2>
          <p>
            The Service is not intended for use by anyone under the age of 18. We do not 
            knowingly collect personal information from children. If we become aware that 
            we have collected data from a child, we will take steps to delete it promptly.
          </p>
        </section>

        <section className="privacy-section">
          <h2>13. International Data Transfers</h2>
          <p>
            Your information may be transferred to and processed in countries other than 
            your own. We ensure appropriate safeguards are in place to protect your data 
            in accordance with applicable data protection laws.
          </p>
        </section>

        <section className="privacy-section">
          <h2>14. Changes to This Policy</h2>
          <p>
            We may update this Privacy Policy from time to time. We will notify you of 
            any material changes by posting the new policy on this page and updating the 
            "Last updated" date. Your continued use of the Service after changes are posted 
            constitutes your acceptance of the updated policy.
          </p>
        </section>

        <section className="privacy-section">
          <h2>15. Contact Us</h2>
          <p>
            If you have any questions about this Privacy Policy or our data practices, 
            please contact us at:
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

export default PrivacyPolicy;
