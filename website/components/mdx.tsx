import defaultMdxComponents from "fumadocs-ui/mdx";
import { Accordion, Accordions } from "fumadocs-ui/components/accordion";
import type { MDXComponents } from "mdx/types";
import { Mermaid } from "@/components/mermaid";
import { SpeakPreview } from "@/components/speak-preview";

export function getMDXComponents(components?: MDXComponents) {
  return {
    ...defaultMdxComponents,
    Accordion,
    Accordions,
    Mermaid,
    SpeakPreview,
    ...components,
  } satisfies MDXComponents;
}
