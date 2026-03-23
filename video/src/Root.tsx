import "./index.css";
import { Composition } from "remotion";
import { MyComposition } from "./Composition";
import { FeatureDeepDive } from "./FeatureDeepDive";
import { CinematicVideo } from "./Cinematic";

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
    </>
  );
};
