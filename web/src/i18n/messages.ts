/** Shared message tree type for locale catalogs. */

export type MessageTree = { [key: string]: string | MessageTree };
export type Messages = MessageTree;
