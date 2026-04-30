import "./index.css";
import { Composition } from "remotion";
import { MyComposition } from "./Composition";
import { FeatureDeepDive } from "./FeatureDeepDive";
import { CinematicVideo } from "./Cinematic";
import { AppDemoShowcase } from "./AppDemoShowcase";
import { SocialClip } from "./SocialClip";
import { AIExplainer } from "./AIExplainer";
import { Walkthrough3D } from "./Walkthrough3D";
import { Social1_POV, Social2_Price, Social3_Demo, Social4_Listicle, Social5_Speedrun } from "./SocialPack";
import { Social6_IMessage, Social7_BeforeAfter, Social8_Reviews, Landscape1_HowItWorks, Landscape2_Stats } from "./SocialPack2";
import { Social9_PlumberScene, Social10_Competitor, Social11_MoneyCounter, Landscape3_DayTimeline, Landscape4_PhoneStorm } from "./SocialPack3";
import { Social12_WouldYouRather, Social13_GuessPrice, Social14_YourWeek, Landscape5_Domino, Landscape6_Bingo } from "./SocialPack4";
import { Social15_Storytime, Social16_TheMath, Social17_SwipeRight, Landscape7_WarRoom, Landscape8_YearReview } from "./SocialPack5";
// Premium pack — intentionally new visual languages (not reused from SocialPack*)
import {
  Editorial_Headline,
  SplitFlap_Metrics,
  IsoCity_CallFunnel,
  MacApp_Cursor,
  Newsroom_Breaking,
} from "./EditorialPack";
import {
  Kinetic_Typography,
  Voicemail_LiveTrans,
  Noir_Split,
  Whiteboard_Annotated,
  Liquid_Blob_Close,
} from "./PremiumPack";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="BookedForYou"
        component={MyComposition}
        durationInFrames={870}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="FeatureDeepDive"
        component={FeatureDeepDive}
        durationInFrames={1425}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="Cinematic"
        component={CinematicVideo}
        durationInFrames={1585}
        fps={30}
        width={1920}
        height={1080}
      />
      {/* NEW: App Demo Showcase — programmatic rendering of real dashboard UI */}
      <Composition
        id="AppDemoShowcase"
        component={AppDemoShowcase}
        durationInFrames={1300}
        fps={30}
        width={1920}
        height={1080}
      />
      {/* NEW: Social Media Clip — vertical format for Reels/TikTok/Shorts */}
      <Composition
        id="SocialClip"
        component={SocialClip}
        durationInFrames={450}
        fps={30}
        width={1080}
        height={1920}
      />
      {/* NEW: AI Explainer — how the AI receptionist/booking system works */}
      <Composition
        id="AIExplainer"
        component={AIExplainer}
        durationInFrames={1095}
        fps={30}
        width={1920}
        height={1080}
      />
      {/* NEW: 3D Walkthrough — real app screenshots with 3D camera movements */}
      <Composition
        id="3DWalkthrough"
        component={Walkthrough3D}
        durationInFrames={1420}
        fps={30}
        width={1920}
        height={1080}
      />
      {/* Social Pack — 5 vertical videos for Instagram/TikTok */}
      <Composition id="Social-POV" component={Social1_POV} durationInFrames={350} fps={30} width={1080} height={1920} />
      <Composition id="Social-Price" component={Social2_Price} durationInFrames={315} fps={30} width={1080} height={1920} />
      <Composition id="Social-Demo" component={Social3_Demo} durationInFrames={360} fps={30} width={1080} height={1920} />
      <Composition id="Social-Listicle" component={Social4_Listicle} durationInFrames={350} fps={30} width={1080} height={1920} />
      <Composition id="Social-Speedrun" component={Social5_Speedrun} durationInFrames={320} fps={30} width={1080} height={1920} />
      {/* Social Pack 2 — more unique formats */}
      <Composition id="Social-IMessage" component={Social6_IMessage} durationInFrames={330} fps={30} width={1080} height={1920} />
      <Composition id="Social-BeforeAfter" component={Social7_BeforeAfter} durationInFrames={200} fps={30} width={1080} height={1920} />
      <Composition id="Social-Reviews" component={Social8_Reviews} durationInFrames={240} fps={30} width={1080} height={1920} />
      {/* Landscape videos */}
      <Composition id="Landscape-HowItWorks" component={Landscape1_HowItWorks} durationInFrames={230} fps={30} width={1920} height={1080} />
      <Composition id="Landscape-Stats" component={Landscape2_Stats} durationInFrames={310} fps={30} width={1920} height={1080} />
      {/* Social Pack 3 — animated scenes */}
      <Composition id="Social-PlumberScene" component={Social9_PlumberScene} durationInFrames={300} fps={30} width={1080} height={1920} />
      <Composition id="Social-Competitor" component={Social10_Competitor} durationInFrames={370} fps={30} width={1080} height={1920} />
      <Composition id="Social-MoneyCounter" component={Social11_MoneyCounter} durationInFrames={300} fps={30} width={1080} height={1920} />
      <Composition id="Landscape-DayTimeline" component={Landscape3_DayTimeline} durationInFrames={310} fps={30} width={1920} height={1080} />
      <Composition id="Landscape-PhoneStorm" component={Landscape4_PhoneStorm} durationInFrames={280} fps={30} width={1920} height={1080} />
      {/* Social Pack 4 */}
      <Composition id="Social-WouldYouRather" component={Social12_WouldYouRather} durationInFrames={230} fps={30} width={1080} height={1920} />
      <Composition id="Social-GuessPrice" component={Social13_GuessPrice} durationInFrames={280} fps={30} width={1080} height={1920} />
      <Composition id="Social-YourWeek" component={Social14_YourWeek} durationInFrames={310} fps={30} width={1080} height={1920} />
      <Composition id="Landscape-Domino" component={Landscape5_Domino} durationInFrames={250} fps={30} width={1920} height={1080} />
      <Composition id="Landscape-Bingo" component={Landscape6_Bingo} durationInFrames={260} fps={30} width={1920} height={1080} />
      {/* Social Pack 5 — longer videos */}
      <Composition id="Social-Storytime" component={Social15_Storytime} durationInFrames={550} fps={30} width={1080} height={1920} />
      <Composition id="Social-TheMath" component={Social16_TheMath} durationInFrames={420} fps={30} width={1080} height={1920} />
      <Composition id="Social-SwipeRight" component={Social17_SwipeRight} durationInFrames={340} fps={30} width={1080} height={1920} />
      <Composition id="Landscape-WarRoom" component={Landscape7_WarRoom} durationInFrames={400} fps={30} width={1920} height={1080} />
      <Composition id="Landscape-YearReview" component={Landscape8_YearReview} durationInFrames={520} fps={30} width={1920} height={1080} />

      {/* ═════ NEW PREMIUM PACK — 10 fundamentally different videos ═════ */}
      {/* Landscape (1920x1080) */}
      <Composition id="Premium-Editorial"   component={Editorial_Headline}  durationInFrames={890} fps={30} width={1920} height={1080} />
      <Composition id="Premium-SplitFlap"   component={SplitFlap_Metrics}   durationInFrames={330} fps={30} width={1920} height={1080} />
      <Composition id="Premium-IsoCity"     component={IsoCity_CallFunnel}  durationInFrames={460} fps={30} width={1920} height={1080} />
      <Composition id="Premium-MacApp"      component={MacApp_Cursor}       durationInFrames={700} fps={30} width={1920} height={1080} />
      <Composition id="Premium-Newsroom"    component={Newsroom_Breaking}   durationInFrames={660} fps={30} width={1920} height={1080} />
      {/* Vertical (1080x1920) */}
      <Composition id="Premium-Kinetic"     component={Kinetic_Typography}  durationInFrames={360} fps={30} width={1080} height={1920} />
      <Composition id="Premium-Voicemail"   component={Voicemail_LiveTrans} durationInFrames={650} fps={30} width={1080} height={1920} />
      <Composition id="Premium-Noir"        component={Noir_Split}          durationInFrames={620} fps={30} width={1080} height={1920} />
      <Composition id="Premium-Whiteboard"  component={Whiteboard_Annotated} durationInFrames={770} fps={30} width={1080} height={1920} />
      <Composition id="Premium-LiquidBlob"  component={Liquid_Blob_Close}   durationInFrames={450} fps={30} width={1080} height={1920} />
    </>
  );
};
