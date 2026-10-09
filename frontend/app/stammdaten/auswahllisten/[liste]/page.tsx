import MasterDataSectionView from "@/components/master-data/MasterDataSectionView";

export default function LookupListPage({ params }: { params: { liste: string } }) {
  return <MasterDataSectionView slug={`auswahllisten/${params.liste}`} />;
}
