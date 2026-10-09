import { redirect } from "next/navigation";

// Teil von „Fristen & Aufgaben“.
export default function Redirect() {
  redirect("/fristen?ansicht=aufgaben");
}
