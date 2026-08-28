import {
  ClipboardList,
  GraduationCap,
  Mail,
  MapPin,
  Phone,
  Presentation,
  StickyNote,
  type LucideIcon,
} from 'lucide-react';

const ICONS: Record<string, LucideIcon> = {
  'map-pin': MapPin,
  phone: Phone,
  mail: Mail,
  presentation: Presentation,
  'graduation-cap': GraduationCap,
  'sticky-note': StickyNote,
};

interface ActivityTypeIconProps {
  icon: string | undefined;
  className?: string;
}

/** Maps the master's lucide icon name to a component; unknown names fall back to a list icon. */
export function ActivityTypeIcon({ icon, className = 'size-5' }: ActivityTypeIconProps) {
  const Icon = (icon ? ICONS[icon] : undefined) ?? ClipboardList;
  return <Icon className={className} aria-hidden="true" />;
}
