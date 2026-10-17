// Club profile route (opened from Standings rows). Spec §8.2 Club profile.
import { useLocalSearchParams } from 'expo-router';
import { ClubProfile } from '../../ui/ClubProfile';

export default function ClubRoute() {
  const { id } = useLocalSearchParams<{ id: string }>();
  return <ClubProfile clubId={id} />;
}
