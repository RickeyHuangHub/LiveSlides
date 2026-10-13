export interface TenantConfig {
  id: string;
  name: string;
  logoUrl: string;
  slogan: string;
  primaryColor: string;
  backgroundUrl: string;
}
export interface CatalogConfig {
  id: string;
  tenantId: string;
  title: string;
  mediaType: 'album' | 'video';
  albumId: string;
  videoUrl: string;
  musicUrl?: string;
  musicName?: string;
  musicVolume?: number;
}
export interface ConfigStore { tenants: TenantConfig[]; catalogs: CatalogConfig[] }
