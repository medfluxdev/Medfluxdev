import MasterDataSectionView from "@/components/master-data/MasterDataSectionView";

export default function MasterDataSectionPage({ params }: { params: { bereich: string } }) {
  return <MasterDataSectionView slug={params.bereich} />;
}
