// inject username/pwd

test('renders with mocked props', async ({ mount }) => {
  const component = await mount(<UserCard user={{ id: 1, name: 'Test User' }} />);
  await expect(component).toContainText('Test User');
});