import { Avatar, AvatarFallback, AvatarImage } from './ui/avatar';
import { Button } from './ui/button';
import { Popover, PopoverContent, PopoverTrigger } from './ui/popover';
import { useAuth } from '../contexts/AuthContext';
import { LogOut, User } from 'lucide-react';

export function UserAvatar() {
  const { user, logout, isAuthenticated } = useAuth();

  if (!isAuthenticated || !user) return null;

  const getProviderLabel = (provider: string) => {
    switch (provider) {
      case 'google':
        return 'Google';
      case 'line':
        return 'LINE';
      case 'facebook':
        return 'Facebook';
      default:
        return provider;
    }
  };

  const getProviderColor = (provider: string) => {
    switch (provider) {
      case 'google':
        return 'bg-red-100 text-red-700';
      case 'line':
        return 'bg-green-100 text-green-700';
      case 'facebook':
        return 'bg-blue-100 text-blue-700';
      default:
        return 'bg-gray-100 text-gray-700';
    }
  };

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="ghost" className="h-8 w-8 rounded-full p-0">
          <Avatar className="h-8 w-8">
            <AvatarImage src={user.picture} alt={user.name} />
            <AvatarFallback className="bg-[#1E5B8C] text-white text-xs">
              {user.name?.charAt(0)?.toUpperCase() || <User className="h-4 w-4" />}
            </AvatarFallback>
          </Avatar>
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-64" align="end">
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <Avatar className="h-12 w-12">
              <AvatarImage src={user.picture} alt={user.name} />
              <AvatarFallback className="bg-[#1E5B8C] text-white">
                {user.name?.charAt(0)?.toUpperCase() || <User className="h-5 w-5" />}
              </AvatarFallback>
            </Avatar>
            <div className="flex flex-col gap-1">
              <span className="font-medium text-sm">{user.name}</span>
              {user.email && (
                <span className="text-xs text-muted-foreground truncate max-w-[140px]">
                  {user.email}
                </span>
              )}
              <span
                className={`text-xs px-2 py-0.5 rounded-full w-fit ${getProviderColor(user.provider)}`}
              >
                {getProviderLabel(user.provider)}
              </span>
            </div>
          </div>
          <hr className="border-t" />
          <Button
            variant="ghost"
            className="w-full justify-start gap-2 text-red-600 hover:text-red-700 hover:bg-red-50"
            onClick={logout}
          >
            <LogOut className="h-4 w-4" />
            登出
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
